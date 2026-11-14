from pathlib import Path

import pytest

from tools.vivo_stock_research.observe import (
    build_timeline,
    capture_phase,
    parse_camera_dump,
    phase_commands,
)


def test_capture_phase_commands_are_read_only(tmp_path):
    commands = phase_commands("before", "com.android.camera")
    assert all(cmd[0] == "shell" for cmd in commands)
    assert not any("force-stop" in " ".join(cmd) for cmd in commands)
    assert any("dumpsys media.camera" in " ".join(cmd) for cmd in commands)


def test_parse_camera_dump_extracts_fps_and_stabilization(tmp_path):
    dump = tmp_path / "camera.txt"
    dump.write_text("aeTargetFpsRange=[60,60]\nvideoStabilizationMode=ON\n")
    parsed = parse_camera_dump(dump)
    assert parsed["aeTargetFpsRange"] == "[60,60]"
    assert parsed["videoStabilizationMode"] == "ON"


def test_build_timeline_writes_table(tmp_path):
    before = tmp_path / "before"
    during = tmp_path / "during"
    before.mkdir()
    during.mkdir()
    (before / "camera.txt").write_text("aeTargetFpsRange=[30,30]\n")
    (during / "camera.txt").write_text(
        "aeTargetFpsRange=[60,60]\nvideoStabilizationMode=ON\n"
    )
    (during / "thermal.txt").write_text("Thermal Status: 2\n")
    out = build_timeline({"before": before, "during": during}, tmp_path / "timeline.md")
    text = out.read_text()
    assert "| before |" in text
    assert "| during |" in text
    assert "[60,60]" in text
    assert "ON" in text
    assert "2" in text


def test_phase_commands_reject_unknown_phase():
    with pytest.raises(ValueError):
        phase_commands("sideways", "com.android.camera")


def test_capture_phase_rejects_unknown_phase(tmp_path):
    with pytest.raises(ValueError):
        capture_phase("adb", "sideways", tmp_path)
