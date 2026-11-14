from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "docs/device-notes/vivo-s50-probe-spec.md"


def test_probe_spec_names_experiments_and_restore():
    text = SPEC.read_text()
    for name in ("Yuv60Probe", "EisProbe", "VivoClassProbe"):
        assert name in text
    assert "finally" in text
    assert "restore" in text.lower()


def test_probe_spec_is_conditional_on_decision_a():
    text = SPEC.read_text()
    assert "Decision: A" in text
    assert "not executed" in text.lower()
    assert "58 fps" in text
