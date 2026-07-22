from __future__ import annotations

import enum
from typing import get_args

from pydantic import BaseModel

from ..config.annotations import Beginner, Display, General, Hidden
from ..midi import Midi
from ..scale.tuning import Tuning, Type
from .control_panel_metadata import (
    _annotation_types,
    _control_metadata,
    _has_metadata,
    _numeric_metadata,
    _options_metadata,
)


def _midi_child_title(data: BaseModel, name: str) -> str:
    if isinstance(data, Midi):
        return {'input': 'in', 'output': 'out'}.get(name, name)
    return name


def _visible_field_names(data: BaseModel) -> tuple[str, ...]:
    cls = type(data)
    return tuple(
        name
        for name in cls.model_fields
        if _is_visible_field(cls, name)
        and not _has_metadata(cls, name, Hidden)
        and not _has_metadata(cls, name, General)
    )


def _is_visible_field(cls: type[BaseModel], name: str) -> bool:
    return not _is_suppressed_field(cls, name)


def _visible_control_names(data: BaseModel, advanced: bool = True) -> list[str]:
    if isinstance(data, Tuning):
        return [
            name
            for name in _visible_tuning_control_names(data)
            if advanced or _is_beginner_field(data, name)
        ]

    return [
        name
        for name in _visible_field_names(data)
        if not isinstance(getattr(data, name), BaseModel)
        and (advanced or _is_beginner_field(data, name))
    ]


def _visible_child_names(data: BaseModel, advanced: bool = True) -> list[str]:
    if isinstance(data, Tuning):
        return (
            ['computed']
            if _active_tuning_type(data) is Type.computed
            and data.computed is not None
            and _has_visible_fields(data.computed, advanced)
            else []
        )

    return [
        name
        for name in _visible_field_names(data)
        if isinstance(getattr(data, name), BaseModel)
        and _has_visible_fields(getattr(data, name), advanced)
    ]


def _has_visible_fields(data: BaseModel, advanced: bool = True) -> bool:
    return bool(
        _visible_control_names(data, advanced)
        or any(
            _has_visible_fields(getattr(data, name), advanced)
            for name in _visible_child_names(data, advanced)
        )
    )


def _visible_tuning_control_names(data: Tuning) -> list[str]:
    names = ['type', 'detune', 'root_frequency', 'root_note']
    match _active_tuning_type(data):
        case Type.table:
            names.append('table')
        case Type.ratios:
            names.append('ratios')
    return names


def _active_tuning_type(data: Tuning) -> Type:
    return data.type or Type.computed


def _is_beginner_field(data: BaseModel, name: str) -> bool:
    return _has_metadata(type(data), name, Beginner)


def _model_tree(data: BaseModel) -> list[BaseModel]:
    models = [data]
    for name in type(data).model_fields:
        if _is_suppressed_field(type(data), name):
            continue
        if _has_metadata(type(data), name, Hidden):
            continue
        child = getattr(data, name)
        if isinstance(child, BaseModel):
            models.extend(_model_tree(child))
    return models


def _is_wide_field(data: BaseModel, name: str) -> bool:
    value = getattr(data, name)
    annotation = type(data).model_fields[name].annotation
    return not (
        _control_metadata(type(data), name).width
        or _numeric_metadata(type(data), name).width
        or isinstance(value, bool | int | float | enum.Enum)
        or _options_metadata(type(data), name)
    ) and (str in _annotation_types(annotation) or isinstance(value, list | dict))


def _is_suppressed_field(cls: type[BaseModel], name: str) -> bool:
    if _has_metadata(cls, name, Display):
        return False
    annotation = cls.__annotations__.get(name, '')
    return str(annotation).startswith('tyro.conf.Suppress') or 'Suppress' in {
        str(i) for i in get_args(annotation)
    }
