from pathlib import Path

import pytest

from tools.vivo_stock_research.manifest import allowed_remote, output_path, parse_ls_z, targets


def test_targets_include_pd2527_and_exclude_app_data():
    items = targets("PD2527_A_16.0.19.12.W10")
    remotes = {item.remote for item in items}
    assert "/vendor/etc" in remotes
    assert "/vendor/bin/hw" in remotes
    assert "/system/lib64/libcameraservice.so" in remotes
    assert not any(path.startswith("/data/data/") for path in remotes)


def test_output_path_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        output_path(tmp_path, "/vendor/etc/../../data/data/com.android.camera")


def test_parse_ls_z_extracts_selinux_context():
    meta = parse_ls_z(
        "-rw-r--r-- 1 root root u:object_r:vendor_configs_file:s0 1234 "
        "2026-11-14 10:00 /vendor/etc/camera/x.json"
    )
    assert meta.mode == "-rw-r--r--"
    assert meta.selinux == "u:object_r:vendor_configs_file:s0"
    assert meta.size == 1234
    assert meta.owner == "root"
    assert meta.group == "root"


def test_allowed_remote_rejects_private_data():
    allowed = [
        "/vendor/etc/camera/PD2527.json",
        "/system/lib64/libcameraservice.so",
        "/data/anr/traces.txt",
    ]
    denied = [
        "/data/data/com.android.camera/x",
        "/data/vendor/camera/x",
        "/data/misc/camera/x",
        "/data/system/dropbox/x",
    ]
    assert all(allowed_remote(path) for path in allowed)
    assert not any(allowed_remote(path) for path in denied)


def test_output_path_maps_absolute_remote_beneath_root(tmp_path):
    result = output_path(tmp_path, "/vendor/etc/camera/x.json")
    assert result == tmp_path / "vendor/etc/camera/x.json"


def test_parse_ls_z_rejects_short_line():
    with pytest.raises(ValueError):
        parse_ls_z("-rw-r--r-- 1 root root")
