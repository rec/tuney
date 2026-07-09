from __future__ import annotations

import enum
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def serialize(data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, item in data.items()
        if (value := _serialize(item)) is not None
    }


def _serialize(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return serialize(value)
    if isinstance(value, tuple):
        return [_serialize(v) for v in value]
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value
