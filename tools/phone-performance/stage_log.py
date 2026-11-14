#!/usr/bin/env python3
"""Parse Rawr still-pipeline stage lines from validation/logcat text.

The capture diagnostics are split between two sinks:

* ``files/rawrcam_validation_current.txt`` carries demosaic/render stage lines
  (``AMAZE_STILL_*``, ``STILL_QUEUE_*``, ...).
* logcat carries the direct ``RawrCamNative`` lines (``STILL_READBACK_MEMORY``,
  ``CAPTURE_SHARPENING``, ``JPEG_*``).

This module deliberately accepts either sink and ignores unrelated lines, so
a combined file works too.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

KNOWN_TAGS = (
    "AMAZE_STILL_PROCESS_PASS",
    "AMAZE_STILL_INIT_PIPELINE_PASS",
    "AMAZE_STILL_INIT_BEGIN",
    "RCD_STILL_PROCESS_PASS",
    "RCD_STILL_INIT_PIPELINE_PASS",
    "RCD_STILL_INIT_BEGIN",
    "VNG4_STILL_PROCESS_PASS",
    "RCDVNG_STILL_INIT_BEGIN",
    "RCDVNG_STILL_INIT_PIPELINE_PASS",
    "RCDVNG_STILL_PROCESS_PASS",
    "STILL_RENDER_ENGINE",
    "STILL_QUEUE_JOB_STARTED",
    "STILL_QUEUE",
    "STILL_READBACK_MEMORY",
    "CAPTURE_SHARPENING",
    "JPEG_UHDR_ENCODE",
    "JPEG_UHDR_FIT",
    "JPEG_STRIPS",
    "JPEG_CAPTURE_WRITE_PASS",
    "JPEG_CAPTURE_WRITE_STARTED",
    "DNG_CAPTURE_WRITE_PASS",
    "CAPTURE_JPEG_PUBLISHED",
)

TAG_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in KNOWN_TAGS) + r")\b")
KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)")
NUMBER_RE = re.compile(r"[-+]?(?:\d+\.\d+|\d+)")


@dataclass
class StageRecord:
    tag: str
    values: dict[str, str] = field(default_factory=dict)
    line: str = ""

    def number(self, key: str) -> float | None:
        raw = self.values.get(key)
        if raw is None:
            return None
        match = NUMBER_RE.search(raw)
        return float(match.group(0)) if match else None


def parse_line(line: str) -> StageRecord | None:
    match = TAG_RE.search(line)
    if not match:
        return None
    return StageRecord(match.group(1), dict(KV_RE.findall(line)), line.rstrip("\n"))


def parse_text(text: str) -> list[StageRecord]:
    records: list[StageRecord] = []
    for line in text.splitlines():
        record = parse_line(line)
        if record:
            records.append(record)
    return records


def parse_file(path: str | Path) -> list[StageRecord]:
    return parse_text(Path(path).read_text(errors="replace"))


def _median(values: Iterable[float]) -> float | None:
    values = list(values)
    return round(statistics.median(values), 2) if values else None


def _p95(values: Iterable[float]) -> float | None:
    values = sorted(values)
    if not values:
        return None
    index = min(len(values) - 1, max(0, int(round(0.95 * (len(values) - 1)))))
    return round(values[index], 2)


def summarize(records: Iterable[StageRecord]) -> dict:
    records = list(records)
    demosaic = [r for r in records if r.tag.endswith("_STILL_PROCESS_PASS")]
    demosaic_ms = [r.number("totalMs") for r in demosaic if r.number("totalMs") is not None]
    init_pipeline = [r for r in records if r.tag.endswith("_STILL_INIT_PIPELINE_PASS")]
    render = [r for r in records if r.tag == "STILL_RENDER_ENGINE"]
    render_rebuilt = [
        r for r in render if r.values.get("tonemap") == "rebuilt" or r.values.get("postDemosaic") == "rebuilt"
    ]
    readbacks = [r for r in records if r.tag == "STILL_READBACK_MEMORY"]
    readback_bytes = sorted({r.values.get("bytes") for r in readbacks if r.values.get("bytes")})
    sharpening_ms = [
        r.number("wallMs") for r in records if r.tag == "CAPTURE_SHARPENING" and r.number("wallMs") is not None
    ]
    jpeg_wall_ms = [
        r.number("wallMs") for r in records if r.tag == "JPEG_UHDR_ENCODE" and r.number("wallMs") is not None
    ]
    jpeg_encode_ms = [
        r.number("encodeMs") for r in records if r.tag == "JPEG_CAPTURE_WRITE_PASS" and r.number("encodeMs") is not None
    ]
    fits = [r for r in records if r.tag == "JPEG_UHDR_FIT"]
    shots = len(demosaic)
    return {
        "records": len(records),
        "shots": shots,
        "demosaic_ms": demosaic_ms,
        "demosaic_median_ms": _median(demosaic_ms),
        "demosaic_p95_ms": _p95(demosaic_ms),
        "pipeline_builds": len(init_pipeline),
        "pipeline_builds_after_first": max(0, len(init_pipeline) - 1),
        "render_rebuilds": len(render_rebuilt),
        "render_rebuilds_after_first": max(0, len(render_rebuilt) - 1),
        "readback_events": len(readbacks),
        "readback_bytes": readback_bytes,
        "sharpening_median_ms": _median(sharpening_ms),
        "jpeg_wall_median_ms": _median(jpeg_wall_ms),
        "jpeg_encode_median_ms": _median(jpeg_encode_ms),
        "jpeg_fit_median_ms": _median([r.number("fitMs") for r in fits if r.number("fitMs") is not None]),
        "jpeg_fit_map_px": sorted({r.values.get("mapPx") for r in fits if r.values.get("mapPx")}),
        "jpeg_strips": sorted({r.values.get("strips") for r in records if r.tag == "JPEG_STRIPS"}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="validation/logcat text files")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    records: list[StageRecord] = []
    for path in args.paths:
        records.extend(parse_file(path))
    summary = summarize(records)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
