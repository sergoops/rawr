from pathlib import Path

from tools.vivo_stock_research.matrix_check import (
    EXPECTED_FEATURES,
    VERDICTS,
    read_matrix,
)

ROOT = Path(__file__).resolve().parents[3]
MATRIX = ROOT / "docs/device-notes/vivo-s50-stock-features.md"
DECISION = ROOT / "docs/device-notes/vivo-s50-60fps-decision.md"


def test_matrix_has_every_row_and_no_empty_evidence():
    matrix = read_matrix(MATRIX)
    assert set(matrix) == set(EXPECTED_FEATURES)
    assert all(row["evidence"] for row in matrix.values())
    assert all(row["verdict"] in VERDICTS for row in matrix.values())
    assert "TBD" not in MATRIX.read_text()


def test_decision_is_one_of_three():
    text = DECISION.read_text()
    assert any(f"Decision: {choice}" in text for choice in ("A", "B", "C"))
