"""Parse vivo sensor-mode selectors and permission XML into evidence JSON."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

_NUMBER = re.compile(r"(?:[<>]=?|==|=)?\s*(\d+(?:\.\d+)?)")
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


@dataclass(frozen=True)
class SensorMode:
    mode_id: int
    width: int
    height: int
    fps: float
    app_types: tuple[str, ...]
    raw: dict


def _strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas without touching strings."""

    out: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = len(text) if end < 0 else end + 2
            continue
        out.append(char)
        index += 1

    return _TRAILING_COMMA.sub(r"\1", "".join(out))


def _load_json(path: Path) -> object:
    text = path.read_text(errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_strip_jsonc(text))


def _numbers(condition: object) -> tuple[float, ...]:
    if not isinstance(condition, list):
        return ()
    values = []
    for item in condition[1:]:
        match = _NUMBER.search(str(item))
        if match:
            values.append(float(match.group(1)))
    return tuple(values)


def _app_types(condition: object) -> tuple[str, ...]:
    if not isinstance(condition, list):
        return ()
    return tuple(str(item) for item in condition[1:] if item not in {"string", "int", "long"})


def _mode_id(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _record_mode(record: dict) -> SensorMode:
    app_value = record.get("AppType", record.get("appType", record.get("app_types", ())))
    if isinstance(app_value, str):
        app_types = (app_value,)
    elif isinstance(app_value, (list, tuple)):
        app_types = tuple(str(item) for item in app_value)
    else:
        app_types = ()

    return SensorMode(
        mode_id=_mode_id(
            record.get("modeId", record.get("mode_id", record.get("Mode", record.get("id", -1))))
        ),
        width=int(record.get("width", record.get("Width", 0)) or 0),
        height=int(record.get("height", record.get("Height", 0)) or 0),
        fps=float(record.get("fps", record.get("FrameRate", record.get("frameRate", 0))) or 0),
        app_types=app_types,
        raw=record,
    )


def _walk_selector(
    node: object,
    inherited_app: tuple[str, ...],
    inherited_fps: tuple[float, ...],
    inherited_width: int,
    inherited_height: int,
    counter: list[int],
    out: list[SensorMode],
) -> None:
    if not isinstance(node, dict):
        return

    app_types = inherited_app
    fps_values = inherited_fps
    width = inherited_width
    height = inherited_height

    type_name = str(node.get("Type", ""))
    condition = node.get("Condition")
    if type_name == "AppType":
        app_types = _app_types(condition) or inherited_app
    elif type_name == "FrameRate":
        fps_values = _numbers(condition) or inherited_fps
    elif type_name == "Width":
        values = _numbers(condition)
        if values:
            width = int(values[0])
    elif type_name == "Height":
        values = _numbers(condition)
        if values:
            height = int(values[0])

    if "Result" in node and fps_values:
        result = str(node.get("Result"))
        for fps in dict.fromkeys(fps_values):
            counter[0] += 1
            out.append(
                SensorMode(
                    mode_id=_mode_id(node.get("Mode", node.get("modeId", -1))),
                    width=width,
                    height=height,
                    fps=fps,
                    app_types=app_types,
                    raw={"result": result, "source": "selector"},
                )
            )

    children = node.get("UsecaseSelector", node.get("usecaseSelector", ()))
    if isinstance(children, dict):
        children = [children]
    for child in children or ():
        _walk_selector(child, app_types, fps_values, width, height, counter, out)


def load_sensor_modes(path: Path) -> list[SensorMode]:
    data = _load_json(path)
    if isinstance(data, list):
        return [_record_mode(record) for record in data if isinstance(record, dict)]
    if not isinstance(data, dict):
        return []

    for key in ("sensorModes", "SensorModeTable", "sensorModeTable", "modes"):
        records = data.get(key)
        if isinstance(records, list):
            return [_record_mode(record) for record in records if isinstance(record, dict)]

    modes: list[SensorMode] = []
    _walk_selector(data, (), (), 0, 0, [0], modes)
    return modes


def hidden_60_modes(modes: list[SensorMode], app_type: str) -> list[SensorMode]:
    """Return >=60 fps modes whose AppType gate includes ``app_type``.

    The name follows the plan's API: these are the stock-only modes, hidden
    from every app type that is not in the gate.
    """

    return [mode for mode in modes if mode.fps >= 60 and app_type in mode.app_types]


def parse_permissions(xml: Path) -> set[str]:
    root = ET.parse(xml).getroot()
    return {
        element.attrib["name"]
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "permission" and "name" in element.attrib
    }


def find_selector(vendor_etc: Path, model: str) -> list[Path]:
    base = vendor_etc / "camera" / "sensormode-selector"
    exact = base / f"{model}.json"
    if exact.exists():
        return [exact]
    return sorted(vendor_etc.glob(f"**/*{model}*.json"))


def _permission_files(vendor_etc: Path) -> list[Path]:
    root = vendor_etc.parents[1]
    candidates = [
        vendor_etc,
        root / "system/etc/permissions",
        root / "system_ext/etc/permissions",
    ]
    files: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir():
            files.extend(sorted(candidate.rglob("*.xml")))
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor-etc", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="PD2527")
    args = parser.parse_args(argv)

    selectors = find_selector(args.vendor_etc, args.model)
    modes: list[SensorMode] = []
    for selector in selectors:
        modes.extend(load_sensor_modes(selector))

    permissions: set[str] = set()
    sources: list[str] = []
    for xml in _permission_files(args.vendor_etc):
        try:
            permissions.update(parse_permissions(xml))
            sources.append(str(xml))
        except (ET.ParseError, OSError):
            continue

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "sensor-modes.json").write_text(
        json.dumps(
            {
                "selectors": [str(path) for path in selectors],
                "modes": [asdict(mode) for mode in modes if mode.fps >= 60],
            },
            indent=2,
        )
        + "\n"
    )
    (args.out / "permissions.json").write_text(
        json.dumps({"permissions": sorted(permissions), "sources": sources}, indent=2) + "\n"
    )
    print(json.dumps({"selectors": len(selectors), "modes": len(modes), "permissions": len(permissions)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
