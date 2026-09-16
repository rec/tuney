from __future__ import annotations

import enum
import inspect
import json
from functools import cache
from typing import get_args, get_origin

from pydantic import BaseModel, TypeAdapter
from tyro._fields import field_list_from_type_or_callable

from ..config.annotations import Display, Numeric, Options
from ..scale.ratios import Ratios
from ..scale.scale import Scale
from ..scale.table import Table
from ..scale.tuning import Tuning


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


def _annotation_types(annotation: object) -> tuple[object, ...]:
    value = getattr(annotation, '__value__', annotation)
    return (value, *_flatten_type_args(value))


def _expects_json(annotation: object) -> bool:
    args = _flatten_type_args(annotation)
    if str in args:
        return False
    origins = {get_origin(i) or i for i in (annotation, *args)}
    return bool(origins & {list, dict})


def _enum_class(annotation: object, value: object) -> type[enum.Enum] | None:
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation
    if isinstance(value, enum.Enum):
        return type(value)

    for arg in _flatten_type_args(annotation):
        if isinstance(arg, type) and issubclass(arg, enum.Enum):
            return arg
    return None


def _flatten_type_args(annotation: object) -> tuple[object, ...]:
    if get_origin(annotation) is None:
        return ()

    args = get_args(annotation)
    return args + tuple(i for a in args for i in _flatten_type_args(a))


def _field_hover_text(model: type[BaseModel], name: str) -> str:
    return _rewrap_hover_text(_field_help(model, name) or name)


def _rewrap_hover_text(text: str) -> str:
    return '\n\n'.join(' '.join(paragraph.split()) for paragraph in text.split('\n\n'))


@cache
def _field_help(model: type[BaseModel], name: str) -> str | None:
    result = field_list_from_type_or_callable(
        model,
        model(),
        support_single_arg_types=False,
        in_union_context=False,
    )
    if not isinstance(result, tuple):
        return None
    for field in result[1]:
        if field.intern_name == name:
            text = field.helptext
            return text() if callable(text) else text
    return None


def _enum_hover_text(member: enum.Enum) -> str:
    return _enum_member_comments(type(member)).get(member.name, member.name)


@cache
def _enum_member_comments(enum_cls: type[enum.Enum]) -> dict[str, str]:
    try:
        lines, _ = inspect.getsourcelines(enum_cls)
    except (OSError, TypeError):
        return {}

    comments: list[str] = []
    result: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            if comment := stripped.removeprefix('#').removeprefix(':').strip():
                comments.append(comment)
        elif not stripped:
            comments.clear()
        elif name := _enum_member_name(enum_cls, stripped):
            if comments:
                result[name] = '\n'.join(comments)
            comments.clear()
        else:
            comments.clear()
    return result


def _enum_member_name(enum_cls: type[enum.Enum], line: str) -> str | None:
    for name in enum_cls.__members__:
        if line.startswith(f'{name} =') or line.startswith(f'{name}:'):
            return name
    return None


def _parse_entry_value(
    raw: str, annotation: object, old_value: object, name: str = ''
) -> object:
    if raw == '':
        return None
    if isinstance(old_value, Ratios):
        return Ratios(text=raw, name=old_value.name, desc=old_value.desc)
    if isinstance(old_value, Table):
        return Table(text=raw)
    if name in {'table', 'ratios'}:
        return Ratios(text=raw) if name == 'ratios' else Table(text=raw)
    if name == 'intervals' and isinstance(old_value, list):
        return raw
    if isinstance(old_value, list | dict) or _expects_json(annotation):
        return json.loads(raw)
    return raw


def _tuning_expression_text(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, Ratios | Table):
        return value.text
    assert isinstance(value, list | tuple)
    return '; '.join(str(i) for i in value)


def _entry_text(data: BaseModel, name: str, value: object, annotation: object) -> str:
    if isinstance(data, Scale) and name == 'intervals' and isinstance(value, list):
        return ''.join(str(i) for i in value)
    if isinstance(data, Tuning) and name in {'table', 'ratios'}:
        return _tuning_expression_text(value)
    if value is None:
        return ''
    if isinstance(value, list | dict):
        return json.dumps(TypeAdapter(annotation).dump_python(value, mode='json'))
    return str(value)
