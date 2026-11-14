import os
import zipfile
from pathlib import Path

import pytest

from tools.vivo_stock_research.apk_inventory import _manifest, apk_entry_report, extract_assets

APK_PATH = Path(os.environ.get("VIVO_STOCK_APK", "tmp/stock-camera-apk/VivoCamera.apk"))


def test_extract_assets_blocks_zip_slip(tmp_path):
    apk = tmp_path / "x.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("../escape.txt", "x")
    with pytest.raises(ValueError):
        extract_assets(apk, tmp_path / "out", ("assets/", "AndroidManifest.xml"))


def test_extract_assets_writes_only_selected_prefixes(tmp_path):
    apk = tmp_path / "x.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("assets/distortion/PD2527/WOI.txt", "woi")
        zf.writestr("assets/videoadvance/a.json", "{}")
        zf.writestr("classes.dex", "dex")
        zf.writestr("unrelated.bin", "no")

    written = extract_assets(
        apk,
        tmp_path / "out",
        ("assets/distortion/PD2527/", "assets/videoadvance/"),
    )

    assert {path.relative_to(tmp_path / "out").as_posix() for path in written} == {
        "assets/distortion/PD2527/WOI.txt",
        "assets/videoadvance/a.json",
    }
    assert not (tmp_path / "out" / "unrelated.bin").exists()


def test_manifest_accepts_relative_destination(tmp_path, monkeypatch):
    apk = tmp_path / "x.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("assets/distortion/PD2527/WOI.txt", "woi")
    written = extract_assets(apk, tmp_path / "out", ("assets/",))
    monkeypatch.chdir(tmp_path)
    report = _manifest(apk, Path("out"), written)
    assert report["files"][0]["path"] == "assets/distortion/PD2527/WOI.txt"


@pytest.mark.skipif(not APK_PATH.exists(), reason="stock APK is not available in this checkout")
def test_real_apk_has_pd2527_assets():
    report = apk_entry_report(APK_PATH)
    assert report["entries"] > 15_000
    assert report["has_pd2527_woi"] is True
    assert report["has_ldc_packdata"] is True
