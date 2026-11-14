"""Index strings and ELF metadata in pulled vivo camera binaries."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Sequence

DEFAULT_PATTERNS = (
    "vivo.control",
    "forceSensorMode",
    "videoFrameRate",
    "temperature_fps",
    "setUseVivoCamera",
    "useVivoCamera",
    "sensorMode",
    "record.fps",
    "EIS",
)


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout)


def index_binary(path: Path, patterns: Sequence[str]) -> dict[str, list[int]]:
    """Return 1-based ``strings`` line numbers where each pattern occurs."""

    result = _run(["strings", "-a", "-n", "4", str(path)])
    lines = result.stdout.splitlines()
    return {
        pattern: [number for number, line in enumerate(lines, 1) if pattern in line]
        for pattern in patterns
    }


def _is_binary(path: Path) -> bool:
    if path.suffix == ".so":
        return True
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def _tool_summary(args: list[str], patterns: Sequence[str]) -> dict[str, object]:
    result = _run(args)
    lines = result.stdout.splitlines()
    matches = [line for line in lines if any(pattern in line for pattern in patterns)]
    return {
        "command": args,
        "returncode": result.returncode,
        "line_count": len(lines),
        "match_count": len(matches),
        "matches": matches[:50],
        "stderr": result.stderr.strip()[:2000],
    }


def index_report(root: Path, patterns: Sequence[str]) -> dict[str, dict]:
    """Index every ELF-like file below ``root`` and classify evidence strength."""

    report: dict[str, dict] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _is_binary(path):
            continue
        string_matches = index_binary(path, patterns)
        found = [pattern for pattern, lines in string_matches.items() if lines]
        if len(found) == len(patterns):
            evidence = "found"
        elif found:
            evidence = "partial"
        else:
            evidence = "insufficient"

        report[path.relative_to(root).as_posix()] = {
            "static_evidence": evidence,
            "patterns": string_matches,
            "strings": _tool_summary(["strings", "-a", "-n", "4", str(path)], patterns),
            "symbols": _tool_summary(["nm", "-D", "--defined-only", str(path)], patterns),
            "dynamic": _tool_summary(["readelf", "-d", str(path)], patterns),
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--patterns", nargs="*", default=list(DEFAULT_PATTERNS))
    args = parser.parse_args(argv)

    report = index_report(args.root, args.patterns)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    findings = {name: item["static_evidence"] for name, item in report.items()}
    print(json.dumps({"files": len(report), "evidence": findings}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
