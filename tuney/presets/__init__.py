import json
import tomllib
from pathlib import Path
from typing import Any

from typing_extensions import TypeIs

BUILTIN_PRESETS = Path(__file__).resolve().parent
USER_PRESETS = Path.home() / '.config' / 'tuney' / 'presets'
PRESET_SUFFIXES = ['.toml', '.json']
FORBIDDEN_PRESET_FIELDS = ['text', 'text_args']


def is_str_dict(x: Any) -> TypeIs[dict[str, Any]]:
    return isinstance(x, dict) and all(isinstance(k, str) for k in x.keys())


def read_file(path: Path) -> dict[str, Any]:
    data = path.read_text()
    match path.suffix:
        case '.toml':
            result = tomllib.loads(data)
        case '.json':
            result = json.loads(data)
        case _:
            raise ValueError(f'Do not understand file {path}')
    if not is_str_dict(result):
        raise ValueError(f'File {path} does not contain a string dictionary')
    return result


def preset_names() -> list[str]:
    names: list[str] = []
    for directory in [USER_PRESETS, BUILTIN_PRESETS]:
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix in PRESET_SUFFIXES and path.stem not in names:
                names.append(path.stem)
    return names


def read_preset(name: str) -> dict[str, Any]:
    data = read_file(_preset_path(name))
    forbidden = [field for field in FORBIDDEN_PRESET_FIELDS if field in data]
    if forbidden:
        raise ValueError(f'Preset {name} must not contain {", ".join(forbidden)}')
    return data


def merged_data(*data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in data:
        result = _merge_data(result, item)
    return result


def _preset_path(name: str) -> Path:
    if Path(name).name != name:
        raise ValueError(f'Preset names must not contain path separators: {name}')
    for directory in [USER_PRESETS, BUILTIN_PRESETS]:
        for suffix in PRESET_SUFFIXES:
            path = directory / f'{name}{suffix}'
            if path.exists():
                return path
    raise ValueError(f'Unknown preset {name}')


def _merge_data(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        old_value = result.get(key)
        if is_str_dict(old_value) and is_str_dict(value):
            result[key] = _merge_data(old_value, value)
        else:
            result[key] = value
    return result
