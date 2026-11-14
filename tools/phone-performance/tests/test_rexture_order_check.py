from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rexture_order_check import late_merge_starts


def test_detects_late_merge_start():
    lines = [
        "I/RawrCam: CAPTURE_ACCEPTED requestId=42",
        "I/RawrCamNative: REXTURE_TIMING requestId=42 stage=accepted monoMs=1000.000",
        "I/RawrCamNative: REXTURE_TIMING requestId=42 stage=merge_start monoMs=1370.000",
    ]
    assert late_merge_starts(lines, 120.0) == [("42", 370.0)]


def test_accepts_fast_merge_start():
    lines = [
        "I/RawrCam: CAPTURE_ACCEPTED requestId=43",
        "I/RawrCamNative: REXTURE_TIMING requestId=43 stage=accepted monoMs=2000.000",
        "I/RawrCamNative: REXTURE_TIMING requestId=43 stage=merge_start monoMs=2030.000",
    ]
    assert late_merge_starts(lines, 120.0) == []


def test_parses_kotlin_scientific_notation():
    lines = [
        "I/RawrCamCapture: CAPTURE_ACCEPTED requestId=44 requestedNs=1",
        "I/RawrCamCapture: REXTURE_TIMING requestId=44 stage=accepted monoMs=1.55781598471614E8",
        "I/RawrCamNative: REXTURE_TIMING requestId=44 stage=merge_start monoMs=155782019.030",
    ]
    rows = late_merge_starts(lines, 120.0)
    assert len(rows) == 1
    assert abs(rows[0][1] - 420.558386) < 0.001
