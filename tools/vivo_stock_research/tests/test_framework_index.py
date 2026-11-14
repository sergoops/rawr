import zipfile
from pathlib import Path

from tools.vivo_stock_research.framework_index import (
    framework_report,
    index_jar,
    index_vdex,
)


def test_index_jar_finds_class_and_method_names(tmp_path):
    jar = tmp_path / "framework.jar"
    with zipfile.ZipFile(jar, "w") as zf:
        zf.writestr(
            "classes.dex",
            b"android.hardware.vivocamera.VivoCameraManager getInfo setValue open onBufferCallback",
        )
    result = index_jar(
        jar,
        ["VivoCameraManager", "getInfo", "notThere"],
    )
    assert "VivoCameraManager" in result
    assert result["VivoCameraManager"]
    assert result["notThere"] == []


def test_index_vdex_handles_missing_file(tmp_path):
    assert index_vdex(tmp_path / "missing.vdex", ["VivoCameraManager"]) == {}


def test_index_vdex_finds_offsets(tmp_path):
    vdex = tmp_path / "boot.vdex"
    vdex.write_bytes(b"\x00VivoCameraDevice\x00getInfo\x00")
    result = index_vdex(vdex, ["VivoCameraDevice", "missing"])
    assert result["VivoCameraDevice"] == ["vdex@1"]
    assert result["missing"] == []


def test_framework_report_marks_class_not_found(tmp_path):
    framework = tmp_path / "system" / "framework"
    framework.mkdir(parents=True)
    jar = framework / "framework.jar"
    with zipfile.ZipFile(jar, "w") as zf:
        zf.writestr(
            "classes.dex",
            b"Landroid/hardware/vivocamera/VivoCameraManager; "
            b"android.hardware.vivocamera.VivoCameraManager getInfo",
        )
    report = framework_report(tmp_path)
    assert report["classes"]["android.hardware.vivocamera.VivoCameraManager"]["found"] is True
    assert report["classes"]["android.hardware.vivocamera.VivoCameraDevice"]["found"] is False
    assert report["jars"]["framework.jar"]["patterns"]["VivoCameraManager"]
