"""Capture-to-publication benchmark through the actual installed app and scripts/ui.

Run with uv; configure the camera/recipe in the app before collecting paired runs.
The same benchmark APK can select contiguous or segmented JPEG output. This does
not change the recipe. No coordinates, application data clearing, or global log reset.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import queue
import re
import shlex
import statistics
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
EVENT = re.compile(r"CAPTURE_JPEG_PUBLISHED requestId=(\d+) success=(true|false) "
                   r"requestedNs=(\d+) publishedNs=(\d+) elapsedMs=([\d.]+)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="com.rawr.camera.benchmark")
    parser.add_argument("--variant", choices=("contiguous", "segmented"), required=True)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--home-after-last", action="store_true",
                        help="After publication, check camera closure and memory four seconds after Home")
    parser.add_argument("--home-during-capture", action="store_true",
                        help="Send the system Home gesture after shutter; requires exactly one capture")
    parser.add_argument("--no-restart", action="store_true",
                        help="measure the already-foreground app instead of stop/start")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_.]+", args.package) or args.samples < 1 or args.warmups < 0:
        parser.error("invalid package or sample count")
    if args.home_during_capture and (args.samples != 1 or args.warmups != 0):
        parser.error("--home-during-capture requires --samples 1 --warmups 0")
    args.output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, UI_PKG=args.package)

    def adb(*parts: str) -> str:
        return subprocess.run(["adb", *parts], check=True, capture_output=True, text=True, env=env).stdout

    def shell(*parts: str) -> str:
        return adb("shell", shlex.join(parts))

    def ui(*parts: str) -> str:
        return subprocess.run([str(ROOT / "scripts/ui"), *parts], cwd=ROOT, check=True,
                              capture_output=True, text=True, env=env).stdout

    def app_pid() -> str:
        result = subprocess.run(["adb", "shell", "pidof", args.package], capture_output=True,
                                text=True, env=env)
        return result.stdout.strip()

    def camera_active() -> bool:
        report = shell("dumpsys", "media.camera")
        if "Active Camera Clients:" not in report:
            return False
        active = report.split("Active Camera Clients:", 1)[1].split("Allowed user IDs:", 1)[0]
        return args.package in active

    def wait_for_camera(timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if camera_active():
                return
            time.sleep(0.5)
        raise RuntimeError("app camera did not become active")

    def wait_for_stable_pid(timeout: float = 20.0) -> str:
        deadline = time.monotonic() + timeout
        last = ""
        while time.monotonic() < deadline:
            current = app_pid()
            if re.fullmatch(r"\d+", current):
                if current == last:
                    return current
                last = current
            else:
                last = ""
            time.sleep(0.5)
        raise RuntimeError("app process did not become stable")

    original = shell("getprop", "debug.rawr.jpeg_stream").strip()
    logcat: subprocess.Popen[str] | None = None
    records: list[dict] = []
    try:
        shell("setprop", "debug.rawr.jpeg_stream", "0" if args.variant == "contiguous" else "1")
        if args.no_restart:
            pid = wait_for_stable_pid()
        else:
            ui("stop")
            deadline = time.monotonic() + 10.0
            while app_pid():
                if time.monotonic() >= deadline:
                    raise RuntimeError("app process did not stop")
                time.sleep(0.2)
            time.sleep(2.0)
            ui("app")
            pid = wait_for_stable_pid()
        wait_for_camera()
        # Camera HAL reports active before the capture pipeline is ready for the
        # first shutter; give the app a moment or the first tap can be ignored.
        time.sleep(2.0)
        (args.output / "ui-before.txt").write_text(ui("state"))
        (args.output / "thermal-before.txt").write_text(shell("dumpsys", "thermalservice"))
        (args.output / "memory-before.txt").write_text(shell("dumpsys", "meminfo", args.package))
        (args.output / "package.txt").write_text(shell("dumpsys", "package", args.package))
        properties = ("debug.rawr.single_primary_queue", "debug.rawr.preview_inflight",
                      "debug.rawr.mali_fair_queue", "debug.rawr.cached_readback")
        (args.output / "debug-properties.json").write_text(json.dumps(
            {name: shell("getprop", name).strip() for name in properties}, indent=2))
        # Do not filter by --pid: on this device the app process can be
        # replaced after the pid check but before/while logcat attaches, which
        # leaves logcat bound to a stale pid and produces an empty log.  The
        # CAPTURE_JPEG_PUBLISHED token is unique to Rawr, so a global stream is
        # safe and survives an app restart.
        logcat = subprocess.Popen(["adb", "logcat", "-T", "1", "-v", "monotonic"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        time.sleep(1.0)
        if app_pid() != pid:
            raise RuntimeError("app process changed while attaching logcat")
        events: queue.Queue[dict] = queue.Queue()

        def read_log() -> None:
            assert logcat is not None and logcat.stdout is not None
            with (args.output / "logcat.txt").open("w") as log:
                for line in logcat.stdout:
                    log.write(line)
                    log.flush()
                    found = EVENT.search(line)
                    if found:
                        # Global logcat can include other Rawr builds.  Keep only
                        # lines emitted by the process we just stabilized.
                        pid_match = re.match(r"\S+\s+(\d+)\s+", line)
                        if pid_match and int(pid_match.group(1)) != int(pid):
                            continue
                        request, success, start, end, elapsed = found.groups()
                        events.put(dict(requestId=int(request), success=success == "true",
                                        requestedNs=int(start), publishedNs=int(end), elapsedMs=float(elapsed)))

        reader = threading.Thread(target=read_log, daemon=True)
        reader.start()
        seen: set[int] = set()
        for index in range(args.warmups + args.samples):
            event = None
            accepted = False
            for attempt in range(3):
                ui("tap", "capture_shutter")
                if args.home_during_capture:
                    ui("home", "--gesture")
                try:
                    event = events.get(timeout=10)
                except queue.Empty:
                    if app_pid() != pid or logcat.poll() is not None:
                        raise RuntimeError("capture timed out or application process exited; run is incomplete") from None
                    if attempt < 2:
                        time.sleep(1.0)
                        continue
                    raise RuntimeError("capture timed out or application process exited; run is incomplete") from None
                if event["requestId"] in seen:
                    continue
                seen.add(event["requestId"])
                accepted = True
                break
            if not accepted:
                raise RuntimeError("capture retries produced no new request id")
            if not event["success"]:
                raise RuntimeError(f"JPEG publication failed: {event}")
            measured = (event["publishedNs"] - event["requestedNs"]) / 1_000_000
            if not math.isfinite(measured) or measured < 0 or abs(measured - event["elapsedMs"]) > 0.01:
                raise RuntimeError("inconsistent monotonic publication timestamps")
            event.update(sample=index - args.warmups, warmup=index < args.warmups)
            records.append(event)
            (args.output / "captures.json").write_text(json.dumps(records, indent=2) + "\n")
            print(json.dumps(event), flush=True)
        if not args.home_during_capture:
            (args.output / "ui-after.txt").write_text(ui("state"))
        (args.output / "thermal-after.txt").write_text(shell("dumpsys", "thermalservice"))
        (args.output / "memory-after.txt").write_text(shell("dumpsys", "meminfo", args.package))
        if args.home_after_last:
            ui("home")
            time.sleep(4)
            (args.output / "memory-home.txt").write_text(shell("dumpsys", "meminfo", args.package))
            camera = shell("dumpsys", "media.camera")
            (args.output / "camera-home.txt").write_text(camera)
            active = camera.split("Active Camera Clients:", 1)[1].split("Allowed user IDs:", 1)[0]
            if args.package in active:
                raise RuntimeError("Camera remains active four seconds after Home")
        times = sorted(row["elapsedMs"] for row in records if not row["warmup"])
        report = dict(package=args.package, variant=args.variant, samples=len(times), warmups=args.warmups,
                      homeDuringCapture=args.home_during_capture, homeAfterLast=args.home_after_last,
                      medianMs=statistics.median(times), p95Ms=times[math.ceil(0.95 * len(times)) - 1],
                      minMs=min(times), maxMs=max(times))
        (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)
    finally:
        if logcat is not None:
            logcat.terminate()
            try:
                logcat.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logcat.kill()
        try:
            shell("setprop", "debug.rawr.jpeg_stream", original)
        finally:
            if not args.no_restart:
                ui("stop")


if __name__ == "__main__":
    main()
