import argparse
import re
import sys

ACCEPTED = re.compile(r"CAPTURE_ACCEPTED requestId=(\d+)")
TIMING = re.compile(
    r"REXTURE_TIMING requestId=(\d+) stage=(accepted|merge_start) monoMs=([0-9.eE+-]+)"
)


def parse_events(lines):
    events = {}
    for line in lines:
        match = ACCEPTED.search(line)
        if match:
            events.setdefault(match.group(1), {})["accepted"] = 0.0
            continue
        match = TIMING.search(line)
        if match:
            request_id, stage, value = match.groups()
            events.setdefault(request_id, {})[stage] = float(value)
    return events


def late_merge_starts(lines, max_ms):
    result = []
    for request_id, event in parse_events(lines).items():
        if "accepted" not in event or "merge_start" not in event:
            continue
        delta = event["merge_start"] - event["accepted"]
        if delta > max_ms:
            result.append((request_id, delta))
    return sorted(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logcat")
    parser.add_argument("--max-merge-start-ms", type=float, default=120.0)
    args = parser.parse_args()
    with open(args.logcat, encoding="utf-8", errors="replace") as handle:
        rows = late_merge_starts(handle.readlines(), args.max_merge_start_ms)
    for request_id, delta in rows:
        print(f"requestId={request_id} accepted->merge_start={delta:.1f} ms")
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
