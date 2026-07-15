from __future__ import annotations

import enum
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from ..config.display import Display, Numeric, Options


def _control_metadata(cls: type[BaseModel], name: str) -> Display:
    for metadata in cls.model_fields[name].metadata:
        if isinstance(metadata, Display):
            return metadata
    return Display()


def _numeric_metadata(cls: type[BaseModel], name: str) -> Numeric:
    for metadata in cls.model_fields[name].metadata:
        if isinstance(metadata, Numeric):
            return metadata
    return Numeric()


def _options_metadata(cls: type[BaseModel], name: str) -> Options | None:
    for metadata in cls.model_fields[name].metadata:
        if isinstance(metadata, Options):
            return metadata
    return None


def _has_metadata(cls: type[BaseModel], name: str, metadata_type: type[object]) -> bool:
    return any(
        metadata is metadata_type or isinstance(metadata, metadata_type)
        for metadata in cls.model_fields[name].metadata
    )


def _annotation_types(annotation: Any) -> tuple[Any, ...]:
    value = getattr(annotation, '__value__', annotation)
    return (value, *_flatten_type_args(value))


def _expects_json(annotation: Any) -> bool:
    args = _flatten_type_args(annotation)
    if str in args:
        return False
    origins = {get_origin(i) or i for i in (annotation, *args)}
    return bool(origins & {list, dict})


def _enum_class(annotation: Any, value: object) -> type[enum.Enum] | None:
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation
    if isinstance(value, enum.Enum):
        return type(value)

    for arg in _flatten_type_args(annotation):
        if isinstance(arg, type) and issubclass(arg, enum.Enum):
            return arg
    return None


def _flatten_type_args(annotation: Any) -> tuple[Any, ...]:
    if get_origin(annotation) is None:
        return ()

    args = get_args(annotation)
    return args + tuple(i for a in args for i in _flatten_type_args(a))
