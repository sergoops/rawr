"""Target manifest and path safety for read-only vivo stock research."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class Target:
    remote: str
    category: str
    required: bool


@dataclass(frozen=True)
class FileMeta:
    mode: str
    owner: str
    group: str
    selinux: str
    size: int


_ALLOWED_PREFIXES = (
    "/vendor/",
    "/system/",
    "/system_ext/",
    "/product/",
    "/odm/",
    "/apex/",
    "/data/anr/",
    "/data/tombstones/",
)

_DENIED_PREFIXES = (
    "/data/data/",
    "/data/vendor/",
    "/data/misc/",
    "/data/system/",
)


def targets(build: str) -> list[Target]:
    """Return the read-only evidence targets for one device build.

    ``build`` identifies the output directory; the paths themselves are
    model-independent system locations.
    """

    del build  # The build only labels the output tree; paths are system-wide.
    return [
        Target("/vendor/etc", "configs", True),
        Target("/system/etc/permissions", "configs", True),
        Target("/system_ext/etc/permissions", "configs", True),
        Target("/vendor/lib64/hw", "libs", True),
        Target("/vendor/lib64/camera", "libs", True),
        Target("/vendor/bin/hw", "libs", True),
        Target("/system/lib64/libcameraservice.so", "libs", True),
        Target("/system/lib64/libcamera_client.so", "libs", True),
        Target("/system/lib64/libcamera2ndk.so", "libs", True),
        Target("/system/framework/framework.jar", "framework", True),
        Target("/system/framework/services.jar", "framework", True),
        Target("/system/framework/vivo-framework.jar", "framework", False),
        Target("/system/framework/arm64/boot.oat", "framework", False),
        Target("/system/framework/arm64/boot.vdex", "framework", False),
        Target("/system/priv-app/VivoCamera", "apk", False),
        Target("/data/anr", "runtime", False),
        Target("/data/tombstones", "runtime", False),
    ]


def allowed_remote(path: str) -> bool:
    """Return True only for read-only system/vendor paths in scope."""

    if not path.startswith("/"):
        return False
    parts = PurePosixPath(path).parts
    if ".." in parts:
        return False
    if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in _DENIED_PREFIXES):
        return False
    return any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def output_path(root: Path, remote: str) -> Path:
    """Map an absolute remote path beneath ``root`` without escaping it."""

    if not remote.startswith("/"):
        raise ValueError(f"remote path must be absolute: {remote!r}")
    remote_path = PurePosixPath(remote)
    if ".." in remote_path.parts:
        raise ValueError(f"remote path contains '..': {remote!r}")
    if not allowed_remote(remote):
        raise ValueError(f"remote path is outside the read-only scope: {remote!r}")

    relative = remote_path.relative_to("/")
    root_resolved = root.resolve()
    candidate = (root_resolved / Path(*relative.parts)).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"remote path escapes output root: {remote!r}")
    return candidate


def parse_ls_z(line: str) -> FileMeta:
    """Parse one Android ``ls -lZ`` line.

    Android's toybox output is: mode links owner group context size date time
    path. The path may contain spaces, so split only the fixed prefix.
    """

    fields = line.split(None, 8)
    if len(fields) != 9:
        raise ValueError(f"not an ls -lZ line: {line!r}")
    mode, _links, owner, group, selinux, size_text, _date, _time, _path = fields
    try:
        size = int(size_text)
    except ValueError as exc:
        raise ValueError(f"invalid size in ls -lZ line: {line!r}") from exc
    return FileMeta(
        mode=mode,
        owner=owner,
        group=group,
        selinux=selinux,
        size=size,
    )
