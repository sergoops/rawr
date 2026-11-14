#!/usr/bin/env python3
"""Aggregate upstream/current capture benchmark runs into comparison tables."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from statistics import median

PUBLISH = re.compile(
    r"CAPTURE_JPEG_PUBLISHED requestId=(\d+) success=(true|false|1|0) "
    r"requestedNs=(\d+) publishedNs=(\d+) elapsedMs=([0-9.]+)"
)
BURST_FINISHED = re.compile(
    r"BURST_FINISHED requestId=(\d+) acceptedToFinishedMs=([0-9.]+)"
)


def parse_capture_events(lines: list[str]) -> list[dict]:
    events: dict[str, dict] = {}
    finished: dict[str, float] = {}
    for line in lines:
        match = BURST_FINISHED.search(line)
        if match:
            request_id, elapsed = match.groups()
            finished[request_id] = float(elapsed)
            if request_id in events:
                events[request_id]["accepted_to_finished_ms"] = float(elapsed)
            continue
        match = PUBLISH.search(line)
        if match:
            request_id, success, requested_ns, published_ns, elapsed = match.groups()
            if success in ("false", "0"):
                events.pop(request_id, None)
                continue
            event = {
                "requestId": request_id,
                "success": True,
                "requestedNs": int(requested_ns),
                "publishedNs": int(published_ns),
                "jpeg_publish_ms": float(elapsed),
            }
            if request_id in finished:
                event["accepted_to_finished_ms"] = finished[request_id]
            events[request_id] = event
    return list(events.values())


def aggregate(events: list[dict], key: str = "jpeg_publish_ms") -> dict:
    values = sorted(float(event[key]) for event in events if key in event)
    if not values:
        return {"n": 0}
    n = len(values)
    p95_index = max(0, math.ceil(0.95 * n) - 1)
    return {
        "n": n,
        "median": median(values),
        "p95": values[p95_index],
        "min": values[0],
        "max": values[-1],
    }


def load_run(path: Path) -> dict:
    if path.is_dir():
        summary = path / "summary.json"
        if summary.exists():
            data = json.loads(summary.read_text())
            return {
                "n": data.get("samples", 0),
                "median": data.get("medianMs"),
                "p95": data.get("p95Ms"),
                "min": data.get("minMs"),
                "max": data.get("maxMs"),
                "source": str(summary),
            }
        path = path / "logcat.txt"
    lines = path.read_text(errors="replace").splitlines()
    return {**aggregate(parse_capture_events(lines)), "source": str(path)}


def parse_run_spec(spec: str) -> tuple[str, str, Path]:
    version, mode, path = spec.split(":", 2)
    return version, mode, Path(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["aggregate"])
    parser.add_argument("--run", action="append", default=[], metavar="VERSION:MODE:PATH")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    runs = []
    for spec in args.run:
        version, mode, path = parse_run_spec(spec)
        runs.append({"version": version, "mode": mode, **load_run(path)})

    payload = {"runs": runs}
    if args.json:
        args.json.write_text(json.dumps(payload, indent=2) + "\n")
    if args.markdown:
        lines = ["| version | mode | n | median ms | p95 ms | min ms | max ms |", "|---|---:|---:|---:|---:|---:|---:|"]
        for run in runs:
            lines.append(
                f"| {run['version']} | {run['mode']} | {run['n']} | "
                f"{run.get('median', float('nan')):.3f} | {run.get('p95', float('nan')):.3f} | "
                f"{run.get('min', float('nan')):.3f} | {run.get('max', float('nan')):.3f} |"
            )
        args.markdown.write_text("\n".join(lines) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
