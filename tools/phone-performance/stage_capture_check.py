#!/usr/bin/env python3
"""Device acceptance check for still-pipeline persistence.

Collect a validation file (and optionally logcat) from a debug capture run,
then assert that demosaic/render engines are built once and reused afterwards:

    adb shell run-as com.rawr.camera.debug cat files/rawrcam_validation_current.txt > validation.txt
    adb logcat -d -v brief > logcat.txt
    uv run --no-project tools/phone-performance/stage_capture_check.py \
        --validation validation.txt --logcat logcat.txt --min-shots 3

Exit status is 0 only when the persistence invariants hold. The current
single-frame path intentionally fails this check until Stage 1 lands; that is
the red test for the reuse work.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import stage_log


def read_device(package: str, path: str) -> str:
    result = subprocess.run(
        ["adb", "exec-out", "run-as", package, "cat", path],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validation", type=Path, help="rawrcam_validation_current.txt")
    parser.add_argument("--logcat", type=Path, help="logcat text (optional, adds renderer/JPEG lines)")
    parser.add_argument("--from-device", action="store_true", help="pull both files with adb")
    parser.add_argument("--package", default="com.rawr.camera.debug")
    parser.add_argument("--min-shots", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.from_device:
        if not args.validation:
            raise SystemExit("--from-device requires --validation (device path, usually files/rawrcam_validation_current.txt)")
        validation_text = read_device(args.package, str(args.validation))
        try:
            logcat_text = subprocess.run(
                ["adb", "logcat", "-d", "-v", "brief"], check=True, text=True, capture_output=True
            ).stdout
        except subprocess.CalledProcessError:
            logcat_text = ""
    else:
        if not args.validation:
            raise SystemExit("--validation is required")
        validation_text = Path(args.validation).read_text(errors="replace")
        logcat_text = Path(args.logcat).read_text(errors="replace") if args.logcat else ""

    records = stage_log.parse_text(validation_text) + stage_log.parse_text(logcat_text)
    summary = stage_log.summarize(records)
    failures: list[str] = []

    if summary["shots"] < args.min_shots:
        failures.append(f"only {summary['shots']} demosaic shots found; need {args.min_shots}")
    if summary["pipeline_builds_after_first"]:
        failures.append(
            f"demosaic pipeline built {summary['pipeline_builds']} times for {summary['shots']} shots "
            f"({summary['pipeline_builds_after_first']} rebuilds after the first)"
        )
    if summary["render_rebuilds_after_first"]:
        failures.append(
            f"render engine rebuilt {summary['render_rebuilds']} times for {summary['shots']} shots "
            f"({summary['render_rebuilds_after_first']} rebuilds after the first)"
        )

    if args.json:
        print(json.dumps({"summary": summary, "failures": failures}, indent=2, sort_keys=True))
    else:
        print("stage capture check")
        for key in (
            "shots",
            "demosaic_median_ms",
            "demosaic_p95_ms",
            "pipeline_builds",
            "pipeline_builds_after_first",
            "render_rebuilds",
            "render_rebuilds_after_first",
            "readback_events",
            "readback_bytes",
            "sharpening_median_ms",
            "jpeg_encode_median_ms",
            "jpeg_fit_median_ms",
        ):
            print(f"  {key}: {summary[key]}")
        if failures:
            print("FAIL")
            for failure in failures:
                print(f"  - {failure}")
        else:
            print("PASS")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
