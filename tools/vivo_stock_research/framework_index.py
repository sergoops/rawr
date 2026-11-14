"""Index hidden vivo camera classes and methods in pulled framework jars."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Sequence

CLASS_NAMES = (
    "android.hardware.vivocamera.VivoCameraManager",
    "android.hardware.vivocamera.VivoCameraDevice",
    "android.hardware.vivocamera.IVivoCameraDeviceCb",
    "VivoCameraManager",
    "VivoCameraDevice",
    "IVivoCameraDeviceCb",
)
METHOD_NAMES = ("getInfo", "setValue", "open", "onBufferCallback")


def _descriptor(name: str) -> str:
    return "L" + name.replace(".", "/") + ";"


CLASS_PATTERNS = (
    *CLASS_NAMES,
    *(_descriptor(name) for name in CLASS_NAMES),
    *METHOD_NAMES,
)


def _offsets(data: bytes, needle: str) -> list[int]:
    encoded = needle.encode("utf-8")
    if not encoded:
        return []
    offsets: list[int] = []
    start = 0
    while True:
        found = data.find(encoded, start)
        if found < 0:
            return offsets
        offsets.append(found)
        start = found + 1


def index_jar(jar: Path, class_patterns: Sequence[str]) -> dict[str, list[str]]:
    """Return entry@offset matches for class/method names in dex/class entries."""

    result = {pattern: [] for pattern in class_patterns}
    try:
        with zipfile.ZipFile(jar) as archive:
            for entry in archive.namelist():
                if not entry.endswith((".dex", ".class")):
                    continue
                data = archive.read(entry)
                for pattern in class_patterns:
                    result[pattern].extend(
                        f"{entry}@{offset}" for offset in _offsets(data, pattern)
                    )
    except (OSError, zipfile.BadZipFile):
        return result
    return result


def index_vdex(vdex: Path, class_patterns: Sequence[str]) -> dict[str, list[str]]:
    """Scan a raw vdex string pool; return an empty report for a missing file."""

    if not vdex.is_file():
        return {}
    data = vdex.read_bytes()
    return {
        pattern: [f"vdex@{offset}" for offset in _offsets(data, pattern)]
        for pattern in class_patterns
    }


def framework_report(root: Path) -> dict:
    """Build a class/method index for the pills under ``system/framework``."""

    root = root.resolve()
    framework = root / "system" / "framework"
    jars: dict[str, dict] = {}
    if framework.is_dir():
        for jar in sorted(framework.glob("*.jar")):
            matches = index_jar(jar, CLASS_PATTERNS)
            found = sum(len(items) for items in matches.values())
            jars[jar.name] = {
                "path": str(jar),
                "size": jar.stat().st_size,
                "status": "found" if found else "stub_jar",
                "source": "zip_dex_strings",
                "patterns": matches,
                "limitations": "dex/class string pool only; no decompiled signatures",
            }

    boot: dict[str, dict] = {}
    for name in ("boot.oat", "boot.vdex"):
        path = framework / "arm64" / name
        if name.endswith(".vdex"):
            matches = index_vdex(path, CLASS_PATTERNS)
            boot[name] = {
                "path": str(path),
                "status": "found" if matches and any(matches.values()) else "missing_or_empty",
                "source": "raw_vdex_strings",
                "patterns": matches,
                "tool_missing": "vdexExtractor",
            }
        else:
            boot[name] = {
                "path": str(path),
                "status": "present" if path.is_file() else "missing",
                "source": "not_indexed",
                "limitations": "boot.oat is an optimized artifact; vdexExtractor not installed",
            }

    classes: dict[str, dict] = {}
    for name in (*CLASS_NAMES, *METHOD_NAMES):
        if name in CLASS_NAMES:
            needle = _descriptor(name)
        else:
            needle = name
        sources = [
            f"{jar_name}:{needle}"
            for jar_name, jar in jars.items()
            if jar["patterns"].get(needle)
        ]
        classes[name] = {
            "found": bool(sources),
            "status": "found" if sources else "class_not_found",
            "sources": sources,
        }

    return {
        "root": str(root),
        "jars": jars,
        "boot": boot,
        "classes": classes,
        "limitations": (
            "Raw dex/class string scan only. Class presence proves the symbol exists, "
            "not that it is callable without a permission/system-app check. Run jadx "
            "for signatures and caller analysis when available."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    report = framework_report(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    classes = {name: item["status"] for name, item in report["classes"].items()}
    print(json.dumps({"jars": len(report["jars"]), "classes": classes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
