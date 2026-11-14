"""Validate the vivo stock-feature capability matrix and decision."""

from __future__ import annotations

from pathlib import Path

EXPECTED_FEATURES: tuple[str, ...] = (
    "1080p60",
    "4K60",
    "1080p120/240",
    "EIS",
    "OIS",
    "10-bit/LOG",
    "HDR/HLG",
    "SAT/full-res",
    "night",
    "portrait/bokeh",
    "8K",
)

VERDICTS: tuple[str, ...] = (
    "supported_by_public_api",
    "needs_vendor_key",
    "needs_privileged_or_system",
    "not_accessible",
    "unknown",
)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def read_matrix(path: Path) -> dict[str, dict[str, str]]:
    """Parse a Markdown matrix keyed by feature.

    The table must contain ``Feature``, ``Evidence`` (or ``Stock evidence``),
    and ``Verdict`` columns.  Header matching is case-insensitive.
    """

    path = Path(path)
    if not path.is_file():
        return {}

    rows: dict[str, dict[str, str]] = {}
    header: list[str] | None = None
    for line in path.read_text().splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if header is None:
            header = [cell.lower() for cell in cells]
            continue
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        record = dict(zip(header, cells, strict=False))
        feature = record.get("feature", "")
        if not feature:
            continue
        rows[feature] = {
            "evidence": record.get("evidence", record.get("stock evidence", "")),
            "verdict": record.get("verdict", ""),
        }
    return rows
