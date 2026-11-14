from pathlib import Path

from tools.vivo_stock_research.binary_index import index_binary, index_report


def test_index_binary_finds_patterns_and_line_numbers(tmp_path):
    blob = tmp_path / "camera.so"
    blob.write_bytes(b"....vivo.control.videoFrameRate....forceSensorMode....")
    result = index_binary(blob, ["vivo.control", "forceSensorMode", "not.there"])
    assert result["vivo.control"] == [1]
    assert result["forceSensorMode"] == [1]
    assert result["not.there"] == []


def test_index_report_marks_stripped_binary(tmp_path):
    blob = tmp_path / "stripped.so"
    blob.write_bytes(b"\x00\x01\x02")
    report = index_report(tmp_path, ["vivo.control"])
    assert report["stripped.so"]["static_evidence"] == "insufficient"


def test_index_report_marks_partial_when_some_patterns_match(tmp_path):
    blob = tmp_path / "partial.so"
    blob.write_bytes(b"vivo.control.only")
    report = index_report(tmp_path, ["vivo.control", "forceSensorMode"])
    assert report["partial.so"]["static_evidence"] == "partial"
    assert report["partial.so"]["patterns"]["vivo.control"] == [1]
    assert report["partial.so"]["patterns"]["forceSensorMode"] == []


def test_index_report_ignores_non_elf_bin_assets(tmp_path):
    blob = tmp_path / "asset.bin"
    blob.write_bytes(b"not an elf file")
    report = index_report(tmp_path, ["vivo.control"])
    assert report == {}


def test_index_binary_accepts_relative_path(tmp_path, monkeypatch):
    blob = tmp_path / "relative.so"
    blob.write_bytes(b"vivo.control")
    monkeypatch.chdir(tmp_path)
    result = index_binary(Path("relative.so"), ["vivo.control"])
    assert result["vivo.control"] == [1]
