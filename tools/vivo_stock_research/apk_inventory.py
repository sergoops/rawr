"""Inventory and safely extract selected assets from the stock camera APK."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

DEFAULT_PREFIXES = (
    "assets/distortion/PD2527/",
    "assets/videoadvance/",
    "assets/",
    "AndroidManifest.xml",
    "classes",
    "resources.arsc",
)


def _safe_target(dest: Path, name: str) -> Path:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe APK entry: {name!r}")
    root = dest.resolve()
    target = (root / Path(*path.parts)).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"APK entry escapes destination: {name!r}")
    return target


def extract_assets(apk: Path, dest: Path, prefixes: tuple[str, ...]) -> list[Path]:
    """Extract entries under ``prefixes`` without allowing zip-slip."""

    written: list[Path] = []
    with zipfile.ZipFile(apk) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            target = _safe_target(dest, info.filename)
            if not any(info.filename == prefix or info.filename.startswith(prefix) for prefix in prefixes):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            written.append(target)
    return written


def apk_entry_report(apk: Path) -> dict[str, int | bool]:
    """Return cheap presence/count facts without extracting the APK."""

    with zipfile.ZipFile(apk) as archive:
        names = {info.filename for info in archive.infolist() if not info.is_dir()}
    return {
        "entries": len(names),
        "has_pd2527_woi": "assets/distortion/PD2527/WOI.txt" in names,
        "has_ldc_packdata": "assets/distortion/PD2527/LDC_packdata.dat" in names,
    }


def _manifest(apk: Path, dest: Path, written: list[Path]) -> dict[str, object]:
    dest = dest.resolve()
    files = []
    for path in written:
        data = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(dest).as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {"apk": str(apk), "entry_count": len(files), "files": files}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)

    written = extract_assets(args.apk, args.out, DEFAULT_PREFIXES)
    report = _manifest(args.apk, args.out, written)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"entries": len(written), "manifest": str(args.manifest)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
