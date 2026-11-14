from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_versions import aggregate, parse_capture_events


def test_parses_publish_and_burst_finish():
    lines = [
        "I/RawrCamNative: BURST_FINISHED requestId=7 acceptedToFinishedMs=1900.0 live=1",
        "I/RawrCamCapture: CAPTURE_JPEG_PUBLISHED requestId=7 success=true requestedNs=1000000000 publishedNs=3000000000 elapsedMs=2000.0",
    ]
    events = parse_capture_events(lines)
    assert len(events) == 1
    assert events[0]["requestId"] == "7"
    assert events[0]["jpeg_publish_ms"] == 2000.0
    assert events[0]["accepted_to_finished_ms"] == 1900.0
    assert events[0]["success"] is True


def test_ignores_failed_publish():
    lines = [
        "I/RawrCamCapture: CAPTURE_JPEG_PUBLISHED requestId=8 success=false requestedNs=1000 publishedNs=2000 elapsedMs=1000.0",
    ]
    assert parse_capture_events(lines) == []


def test_aggregate_statistics():
    events = [{"jpeg_publish_ms": x} for x in (10.0, 20.0, 30.0, 40.0)]
    stats = aggregate(events)
    assert stats["n"] == 4
    assert stats["median"] == 25.0
    assert stats["min"] == 10.0
    assert stats["max"] == 40.0
