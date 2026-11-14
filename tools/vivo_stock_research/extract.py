"""Read-only extraction of stock camera evidence over adb."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .manifest import FileMeta, Target, allowed_remote, output_path, parse_ls_z, targets

_CAMERA_PACKAGE = re.compile(r"^(?P<path>package:[^=]+)=(?P<package>.+)$")
_UID = re.compile(r"uid=(\d+)\(")


@dataclass
class ExtractionReport:
    pulled: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)
    files: list[dict[str, object]] = field(default_factory=list)
    build: str = ""
    fingerprint: str = ""


def _run(adb: str, args: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _shell(adb: str, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return _run(adb, ["shell", *args], timeout=timeout)


def preflight(adb: str = "adb") -> dict[str, object]:
    """Verify shell UID and resolve stock camera package paths."""

    ident = _shell(adb, "id")
    match = _UID.search(ident.stdout)
    if match is None or match.group(1) != "2000":
        raise RuntimeError(
            "this tool requires adb UID 2000 (shell), got: "
            f"{(ident.stdout or ident.stderr).strip() or 'no output'}"
        )

    enforce = _shell(adb, "getenforce").stdout.strip()
    fingerprint = _shell(adb, "getprop", "ro.build.fingerprint").stdout.strip()
    packages = _shell(adb, "pm", "list", "packages", "-f")

    package_paths: dict[str, str] = {}
    for line in packages.stdout.splitlines():
        match = _CAMERA_PACKAGE.match(line.strip())
        if match is None:
            continue
        package = match.group("package")
        if "camera" not in package.lower():
            continue
        package_paths[package] = match.group("path").removeprefix("package:")

    return {
        "uid": "2000",
        "enforce": enforce,
        "fingerprint": fingerprint,
        "package_paths": package_paths,
    }


def _reason(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip()


def _sha256_path(path: Path) -> tuple[int, str]:
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.stat().st_size, digest

    digest = hashlib.sha256()
    size = 0
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        data = child.read_bytes()
        digest.update(child.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        size += len(data)
    return size, digest.hexdigest()


def _record(
    report: ExtractionReport,
    target: Target,
    remote: str,
    local: Path,
    meta: FileMeta,
) -> None:
    size, digest = _sha256_path(local)
    report.files.append(
        {
            "remote": remote,
            "local": str(local),
            "category": target.category,
            "kind": "dir" if local.is_dir() else "file",
            "mode": meta.mode,
            "owner": meta.owner,
            "group": meta.group,
            "selinux": meta.selinux,
            "size": size,
            "sha256": digest,
        }
    )


def pull_targets(adb: str, out: Path, selected: list[Target]) -> ExtractionReport:
    report = ExtractionReport()
    out = out.resolve()

    for target in selected:
        remote = target.remote
        stat = _shell(adb, "ls", "-ldZ", remote)
        if stat.returncode != 0:
            reason = _reason(stat) or "unreadable"
            item = {"remote": remote, "category": target.category, "reason": reason}
            if "Permission denied" in reason or not allowed_remote(remote):
                report.skipped.append(item)
            else:
                report.failed.append(item)
            continue

        line = stat.stdout.strip().splitlines()[0] if stat.stdout.strip() else ""
        try:
            meta = parse_ls_z(line)
        except ValueError:
            report.failed.append(
                {
                    "remote": remote,
                    "category": target.category,
                    "reason": f"unexpected ls output: {line!r}",
                }
            )
            continue

        if not allowed_remote(remote):
            report.skipped.append(
                {
                    "remote": remote,
                    "category": target.category,
                    "reason": f"outside allowed read-only scope: {line}",
                }
            )
            continue

        readable = _shell(adb, "test", "-r", remote)
        if readable.returncode != 0:
            report.skipped.append(
                {
                    "remote": remote,
                    "category": target.category,
                    "reason": f"not readable: {line}",
                }
            )
            continue

        local = output_path(out, remote)
        local.parent.mkdir(parents=True, exist_ok=True)
        pull = _run(adb, ["pull", remote, str(local)])
        if pull.returncode != 0:
            report.failed.append(
                {
                    "remote": remote,
                    "category": target.category,
                    "reason": _reason(pull) or "adb pull failed",
                }
            )
            continue

        report.pulled.append(remote)
        _record(report, target, remote, local, meta)

    return report


def write_manifest(out: Path, report: ExtractionReport) -> Path:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "build": report.build,
        "fingerprint": report.fingerprint,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pulled": report.pulled,
        "skipped": report.skipped,
        "failed": report.failed,
        "files": report.files,
    }
    path = out / "manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _selected(build: str, categories: set[str]) -> list[Target]:
    return [target for target in targets(build) if target.category in categories]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--categories", default="configs,framework,libs")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    categories = {item.strip() for item in args.categories.split(",") if item.strip()}
    selected = _selected(args.build, categories)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "build": args.build,
                    "categories": sorted(categories),
                    "targets": [asdict(target) for target in selected],
                },
                indent=2,
            )
        )
        return 0

    info = preflight(args.adb)
    report = pull_targets(args.adb, args.out, selected)
    report.build = args.build
    report.fingerprint = str(info["fingerprint"])
    manifest = write_manifest(args.out, report)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "pulled": len(report.pulled),
                "skipped": len(report.skipped),
                "failed": len(report.failed),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
