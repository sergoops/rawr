import json
from pathlib import Path

import pytest

from tools.vivo_stock_research.extract import (
    ExtractionReport,
    preflight,
    pull_targets,
    write_manifest,
)
from tools.vivo_stock_research.manifest import Target

FIXTURES = Path(__file__).parent / "fixtures"


def test_pull_skips_unreadable_and_records_reason(tmp_path):
    report = pull_targets(
        adb=str(FIXTURES / "fake_adb.sh"),
        out=tmp_path,
        selected=[
            Target("/vendor/etc/camera/PD2527.json", "configs", True),
            Target("/data/data/com.android.camera/x", "data", False),
        ],
    )
    assert "/vendor/etc/camera/PD2527.json" in report.pulled
    assert any("Permission denied" in item["reason"] for item in report.skipped)
    assert not (tmp_path / "data/data/com.android.camera").exists()


def test_preflight_rejects_non_shell_uid():
    with pytest.raises(RuntimeError, match="UID 2000"):
        preflight(adb=str(FIXTURES / "fake_adb_root.sh"))


def test_preflight_resolves_stock_package_paths():
    info = preflight(adb=str(FIXTURES / "fake_adb.sh"))
    assert info["uid"] == "2000"
    assert info["enforce"] == "Enforcing"
    assert "com.android.camera" in info["package_paths"]
    assert info["package_paths"]["com.android.camera"].startswith("/system/")


def test_manifest_records_hashes_and_reasons(tmp_path):
    report = pull_targets(
        adb=str(FIXTURES / "fake_adb.sh"),
        out=tmp_path,
        selected=[Target("/vendor/etc/camera/PD2527.json", "configs", True)],
    )
    report.build = "PD2527_A_16.0.19.12.W10"
    report.fingerprint = "fixture"
    path = write_manifest(tmp_path, report)
    data = json.loads(path.read_text())
    assert data["build"] == "PD2527_A_16.0.19.12.W10"
    assert data["pulled"] == ["/vendor/etc/camera/PD2527.json"]
    assert data["files"][0]["sha256"]
    assert data["files"][0]["size"] > 0


def test_report_defaults_are_independent():
    first = ExtractionReport()
    second = ExtractionReport()
    first.pulled.append("x")
    assert second.pulled == []
