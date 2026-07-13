import json
import tomllib
from pathlib import Path
from typing import Any

import tomlkit
from typing_extensions import TypeIs

from ..config.serialize import serialize

BUILTIN_PRESETS = Path(__file__).resolve().parent
USER_PRESETS = Path.home() / '.config' / 'tuney' / 'presets'
PRESET_SUFFIXES = ['.toml', '.json']
SECTION_PRESET_SUFFIX = '.toml'
SECTION_PRESETS = {'scale', 'tuning'}
FORBIDDEN_PRESET_FIELDS = ['text', 'text_file', 'text_args']
SKIPPED_PRESET_FIELDS = [
    *FORBIDDEN_PRESET_FIELDS,
    'config_file',
    'preset',
]


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
            if (
                path.suffix in PRESET_SUFFIXES
                and not _is_section_preset_path(path)
                and path.stem not in names
            ):
                names.append(path.stem)
    return names


def section_preset_names(section: str) -> list[str]:
    _validate_section(section)
    names: list[str] = []
    suffix = f'.{section}{SECTION_PRESET_SUFFIX}'
    for directory in [USER_PRESETS, BUILTIN_PRESETS]:
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if path.name.endswith(suffix) and (name := path.name[: -len(suffix)]):
                if name not in names:
                    names.append(name)
    return names


def user_preset_names() -> list[str]:
    return _preset_names(USER_PRESETS)


def write_preset(name: str, data: dict[str, object]) -> None:
    path = _user_preset_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {k: v for k, v in data.items() if k not in SKIPPED_PRESET_FIELDS}
    path.write_text(tomlkit.dumps(serialize(values)))


def delete_presets(names: list[str]) -> None:
    for name in names:
        for path in _user_preset_paths(name):
            if path.exists():
                path.unlink()


def user_preset_snapshot() -> dict[str, bytes]:
    if not USER_PRESETS.exists():
        return {}
    return {
        path.name: path.read_bytes()
        for path in sorted(USER_PRESETS.iterdir())
        if path.suffix in PRESET_SUFFIXES
    }


def restore_user_preset_snapshot(snapshot: dict[str, bytes]) -> None:
    USER_PRESETS.mkdir(parents=True, exist_ok=True)
    for path in USER_PRESETS.iterdir():
        if path.suffix in PRESET_SUFFIXES:
            path.unlink()
    for name, data in snapshot.items():
        (USER_PRESETS / name).write_bytes(data)


def read_preset(name: str) -> dict[str, Any]:
    data = read_file(_preset_path(name))
    if forbidden := [field for field in FORBIDDEN_PRESET_FIELDS if field in data]:
        raise ValueError(f'Preset {name} must not contain {", ".join(forbidden)}')
    return data


def read_section_preset(section: str, name: str) -> dict[str, Any]:
    _validate_section(section)
    data = read_file(_section_preset_path(section, name))
    value = data.get(section)
    if not is_str_dict(value):
        raise ValueError(f'Section preset {name} must contain [{section}]')
    return value


def merged_data(*data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in data:
        result = _merge_data(result, item)
    return result


def _preset_path(name: str) -> Path:
    _validate_preset_name(name)
    for directory in [USER_PRESETS, BUILTIN_PRESETS]:
        for suffix in PRESET_SUFFIXES:
            if (
                path := directory / f'{name}{suffix}'
            ).exists() and not _is_section_preset_path(path):
                return path
    raise ValueError(f'Unknown preset {name}')


def _section_preset_path(section: str, name: str) -> Path:
    _validate_section(section)
    _validate_preset_name(name)
    suffix = f'.{section}{SECTION_PRESET_SUFFIX}'
    for directory in [USER_PRESETS, BUILTIN_PRESETS]:
        if (path := directory / f'{name}{suffix}').exists():
            return path
    raise ValueError(f'Unknown {section} preset {name}')


def _user_preset_path(name: str) -> Path:
    _validate_preset_name(name)
    return USER_PRESETS / f'{name}.toml'


def _user_preset_paths(name: str) -> list[Path]:
    _validate_preset_name(name)
    return [USER_PRESETS / f'{name}{suffix}' for suffix in PRESET_SUFFIXES]


def _validate_preset_name(name: str) -> None:
    if not name:
        raise ValueError('Preset name must not be empty')
    if Path(name).name != name:
        raise ValueError(f'Preset names must not contain path separators: {name}')


def _validate_section(section: str) -> None:
    if section not in SECTION_PRESETS:
        raise ValueError(f'Unknown preset section {section}')


def _preset_names(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    names: list[str] = []
    for path in sorted(directory.iterdir()):
        if (
            path.suffix in PRESET_SUFFIXES
            and not _is_section_preset_path(path)
            and path.stem not in names
        ):
            names.append(path.stem)
    return names


def _is_section_preset_path(path: Path) -> bool:
    return any(
        path.name.endswith(f'.{section}{SECTION_PRESET_SUFFIX}')
        for section in SECTION_PRESETS
    )


def _merge_data(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        old_value = result.get(key)
        if is_str_dict(old_value) and is_str_dict(value):
            result[key] = _merge_data(old_value, value)
        else:
            result[key] = value
    return result
