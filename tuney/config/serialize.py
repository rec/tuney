from __future__ import annotations

import enum
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from typing_extensions import TypeIs


def serialize(data: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, item in data.items()
        if (value := _serialize(item)) is not None
    }


def _serialize(value: object) -> object:
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, Path):
        return str(value)
    if _is_str_mapping(value):
        return serialize(value)
    if isinstance(value, tuple):
        return [_serialize(v) for v in value]
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _is_str_mapping(value: object) -> TypeIs[Mapping[str, Any]]:
    return isinstance(value, Mapping) and all(isinstance(k, str) for k in value)
