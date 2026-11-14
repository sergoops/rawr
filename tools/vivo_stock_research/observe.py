"""Capture read-only stock-camera runtime evidence over adb."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

PHASES = ("before", "during", "after")

_KV = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*[:=]\s*(.+?)\s*$")
_THERMAL = re.compile(r"(?i)thermal\s*status\s*[:=]\s*([A-Za-z0-9]+)")


def phase_commands(phase: str, package: str) -> list[list[str]]:
    """Return read-only ``adb shell`` commands for one observation phase."""

    if phase not in PHASES:
        raise ValueError(f"unknown phase: {phase!r}; expected one of {PHASES}")
    del package  # The caller's package is recorded in the phase directory.
    return [
        ["shell", "dumpsys", "media.camera"],
        ["shell", "dumpsys", "media.camera", "-m", "3a"],
        ["shell", "dumpsys", "thermalservice"],
        ["shell", "dumpsys", "media.codec"],
        ["shell", "logcat", "-d", "-b", "all", "-v", "threadtime"],
    ]


def _filename(command: list[str]) -> str:
    joined = " ".join(command)
    if "thermalservice" in joined:
        return "thermal.txt"
    if "media.codec" in joined:
        return "media-codec.txt"
    if "logcat" in joined:
        return "logcat.txt"
    if "-m 3a" in joined:
        return "camera-3a.txt"
    return "camera.txt"


def capture_phase(adb: str, phase: str, out: Path) -> dict[str, Path]:
    """Run one phase and write each command's stdout/stderr to a file."""

    if phase not in PHASES:
        raise ValueError(f"unknown phase: {phase!r}; expected one of {PHASES}")

    phase_dir = out.resolve() / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for command in phase_commands(phase, "com.android.camera"):
        result = subprocess.run(
            [adb, *command],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        path = phase_dir / _filename(command)
        body = result.stdout
        if result.stderr:
            body += "\n[stderr]\n" + result.stderr
        path.write_text(body)
        written[path.name] = path
    return written


def parse_camera_dump(path: Path) -> dict[str, str]:
    """Extract ``key=value`` / ``key: value`` pairs from a camera dump."""

    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    for line in path.read_text(errors="replace").splitlines():
        match = _KV.match(line)
        if match is not None:
            parsed[match.group(1)] = match.group(2)
    return parsed


def _first(parsed: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = parsed.get(key)
        if value:
            return value
    return ""


def _thermal_status(path: Path) -> str:
    if not path.is_file():
        return ""
    match = _THERMAL.search(path.read_text(errors="replace"))
    return match.group(1) if match else ""


def build_timeline(phases: dict[str, Path], out: Path) -> Path:
    """Write a Markdown timeline from captured phase directories."""

    rows: list[list[str]] = []
    for phase in PHASES:
        path = phases.get(phase)
        if path is None:
            continue
        directory = path if path.is_dir() else path.parent
        camera = directory / "camera.txt"
        parsed = parse_camera_dump(camera)
        rows.append(
            [
                phase,
                _first(parsed, "aeTargetFpsRange", "android.control.aeTargetFpsRange"),
                _first(
                    parsed,
                    "videoStabilizationMode",
                    "android.control.videoStabilizationMode",
                ),
                _first(
                    parsed,
                    "opticalStabilizationMode",
                    "android.lens.opticalStabilizationMode",
                ),
                _first(parsed, "sensorMode", "android.control.sensorMode"),
                _thermal_status(directory / "thermal.txt"),
                "yes" if (directory / "watch.txt").is_file() else "no",
            ]
        )

    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "| Phase | AE target FPS range | Video stabilization | "
        "Optical stabilization | Sensor mode | Thermal status | Watch supported |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    body = "".join("| " + " | ".join(row) + " |\n" for row in rows)
    out.write_text("# Stock camera runtime timeline\n\n" + header + body)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--adb", default="adb")
    args = parser.parse_args(argv)

    written = capture_phase(args.adb, args.phase, args.out)
    print(json.dumps({name: str(path) for name, path in written.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
