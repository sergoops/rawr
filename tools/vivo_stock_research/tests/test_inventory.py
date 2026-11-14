from pathlib import Path

import pytest

from tools.vivo_stock_research.inventory import (
    find_selector,
    hidden_60_modes,
    load_sensor_modes,
    parse_permissions,
)

FIXTURES = Path(__file__).parent / "fixtures"
REAL_SELECTOR = Path(
    "tmp/vivo-stock/PD2527_A_16.0.19.12.W10/vendor/etc/camera/"
    "sensormode-selector/PD2527.json"
)


def test_selector_reports_60_modes_hidden_from_third_party():
    modes = load_sensor_modes(FIXTURES / "PD2527.synthetic.json")
    assert [m.mode_id for m in hidden_60_modes(modes, "third_party")] == []
    assert {m.mode_id for m in hidden_60_modes(modes, "vivo")} == {6, 9}


def test_permission_parser_reads_system_camera():
    perms = parse_permissions(FIXTURES / "permissions.synthetic.xml")
    assert "android.permission.SYSTEM_CAMERA" in perms


def test_missing_selector_is_reported(tmp_path):
    assert find_selector(tmp_path, "PD2527") == []


def test_find_selector_locates_model_file(tmp_path):
    target = tmp_path / "camera/sensormode-selector/PD2527.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}")
    assert find_selector(tmp_path, "PD2527") == [target]


@pytest.mark.skipif(not REAL_SELECTOR.exists(), reason="real selector is not pulled")
def test_real_selector_jsonc_parses():
    modes = load_sensor_modes(REAL_SELECTOR)
    assert modes
    assert any(m.fps >= 60 for m in modes)
