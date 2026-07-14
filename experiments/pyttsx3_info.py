from __future__ import annotations

from collections.abc import Mapping, Sequence

import pyttsx3
import tomlkit


def main() -> None:
    engine = pyttsx3.init()
    data = {'voices': [_voice_data(v) for v in engine.getProperty('voices')]}
    print(tomlkit.dumps(data), end='')


def _voice_data(voice: object) -> dict[str, object]:
    names = sorted(set(vars(voice)) | {i for i in dir(voice) if not i.startswith('_')})
    data = {}
    for name in names:
        try:
            value = getattr(voice, name)
        except AttributeError:
            continue
        if not callable(value):
            data[name] = _toml_value(value)
    return data


def _toml_value(value: object) -> object:
    if value is None or isinstance(value, bool | float | int | str):
        return value
    if isinstance(value, bytes):
        return value.decode(errors='replace')
    if isinstance(value, Mapping):
        return {str(k): _toml_value(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_toml_value(i) for i in value]
    return str(value)


if __name__ == '__main__':
    main()
