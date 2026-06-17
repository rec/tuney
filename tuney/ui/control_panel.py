from __future__ import annotations

import enum
import json
import math
from typing import Any, get_args, get_origin

import customtkinter as ctk
from pydantic import BaseModel, ValidationError

FONT = 'Arial', 12
TITLE_FONT = 'Arial', 13, 'bold'
CHECKBOX_SIZE = 14
RADIO_SIZE = 14
TOGGLE_HEIGHT = 18
ENTRY_CHAR_WIDTH = 10
SMALL_FLOAT_FIELDS = {'max_gap', 'gain', 'scale'}
GUI_HIDDEN_FIELDS = {'Tuney': {'config_file', 'text', 'disable_gui'}}


def make_control_panel(
    parent: Any, data: BaseModel, height: int = 200
) -> ctk.CTkScrollableFrame:
    frame = ctk.CTkScrollableFrame(parent, height=height)
    _add_model_controls(frame, data)
    return frame


def _add_model_controls(
    parent: ctk.CTkFrame | ctk.CTkScrollableFrame,
    data: BaseModel,
    title: str | None = None,
) -> None:
    if title:
        ctk.CTkLabel(parent, text=title, font=TITLE_FONT).pack(anchor='w', pady=(8, 2))

    field_names = _visible_field_names(data)
    controls = tuple(
        name for name in field_names if not isinstance(getattr(data, name), BaseModel)
    )
    children = tuple(
        name for name in field_names if isinstance(getattr(data, name), BaseModel)
    )

    if controls:
        _add_control_grid(parent, data, controls)

    for name in children:
        child = getattr(data, name)
        assert isinstance(child, BaseModel)
        section = ctk.CTkFrame(parent)
        section.pack(fill='x', expand=True, pady=(6, 0))
        _add_model_controls(section, child, name)


def _add_control_grid(
    parent: ctk.CTkFrame | ctk.CTkScrollableFrame,
    data: BaseModel,
    fields: tuple[str, ...],
) -> None:
    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(fill='x', expand=True)
    columns = max(1, math.ceil(len(fields) ** 0.5))

    for i, name in enumerate(fields):
        row, column = divmod(i, columns)
        cell = ctk.CTkFrame(frame, border_width=1)
        cell.grid(row=row, column=column, padx=4, pady=4, sticky='nsew')
        frame.grid_columnconfigure(column, weight=1)
        frame.grid_rowconfigure(row, weight=1)

        _add_control(cell, data, name)


def _visible_field_names(data: BaseModel) -> tuple[str, ...]:
    cls = type(data)
    hidden = GUI_HIDDEN_FIELDS.get(cls.__name__, set())
    return tuple(
        name
        for name in cls.model_fields
        if name not in hidden and not _is_suppressed_field(cls, name)
    )


def _is_suppressed_field(cls: type[BaseModel], name: str) -> bool:
    annotation = cls.__annotations__.get(name, '')
    return str(annotation).startswith('tyro.conf.Suppress') or 'Suppress' in {
        str(i) for i in get_args(annotation)
    }


def _add_control(parent: ctk.CTkFrame, data: BaseModel, name: str) -> None:
    value = getattr(data, name)
    annotation = type(data).model_fields[name].annotation
    enum_cls = _enum_class(annotation, value)

    if enum_cls:
        _add_enum_control(parent, data, name, value, enum_cls)
    elif isinstance(value, bool):
        _add_bool_control(parent, data, name, value)
    else:
        _add_entry_control(parent, data, name, value)


def _add_bool_control(
    parent: ctk.CTkFrame, data: BaseModel, name: str, value: bool
) -> None:
    var = ctk.IntVar(parent, int(value))

    def command() -> None:
        _set_model_value(data, name, bool(var.get()))

    ctk.CTkCheckBox(
        parent,
        text=name,
        variable=var,
        command=command,
        font=FONT,
        height=TOGGLE_HEIGHT,
        checkbox_width=CHECKBOX_SIZE,
        checkbox_height=CHECKBOX_SIZE,
    ).pack(anchor='w')


def _add_entry_control(
    parent: ctk.CTkFrame, data: BaseModel, name: str, value: Any
) -> None:
    annotation = type(data).model_fields[name].annotation
    if name == 'alphabet' and value in (None, '') and hasattr(data, 'alphabet_'):
        value = data.alphabet_
    if value is None:
        text = ''
    elif isinstance(value, list | dict):
        text = json.dumps(value)
    else:
        text = str(value)
    var = ctk.StringVar(parent, text)
    width = _entry_width(name, annotation)
    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(fill='x')
    ctk.CTkLabel(frame, text=name, font=FONT).pack(side='left', padx=(0, 4))
    entry = (
        ctk.CTkEntry(frame, width=width, textvariable=var)
        if width
        else ctk.CTkEntry(frame, textvariable=var)
    )
    text_color = entry.cget('text_color')

    def update(*_: Any) -> None:
        raw = var.get()
        try:
            _set_model_value(data, name, _parse_entry_value(raw, annotation, value))
        except ValidationError:
            entry.configure(text_color='red')
            return
        except (TypeError, ValueError):
            entry.configure(text_color='red')
        else:
            entry.configure(text_color=text_color)

    entry.bind('<FocusOut>', update)
    entry.bind('<Return>', update)
    if width:
        entry.pack(side='left')
    else:
        entry.pack(side='left', fill='x', expand=True)


def _add_enum_control(
    parent: ctk.CTkFrame,
    data: BaseModel,
    name: str,
    value: enum.Enum,
    enum_cls: type[enum.Enum],
) -> None:
    members = tuple(enum_cls)
    index = members.index(value) if isinstance(value, enum_cls) else 0
    var = ctk.IntVar(parent, index)

    def command() -> None:
        _set_model_value(data, name, members[var.get()])

    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(anchor='w')
    ctk.CTkLabel(frame, text=name, font=FONT).pack(side='left', padx=(0, 4))
    for i, member in enumerate(members):
        ctk.CTkRadioButton(
            frame,
            text=member.name,
            variable=var,
            value=i,
            command=command,
            font=FONT,
            height=TOGGLE_HEIGHT,
            radiobutton_width=RADIO_SIZE,
            radiobutton_height=RADIO_SIZE,
        ).pack(side='left', padx=(0, 6))


def _set_model_value(data: BaseModel, name: str, value: Any) -> None:
    values = data.model_dump()
    values[name] = value
    validated = type(data).model_validate(values)
    object.__setattr__(data, name, getattr(validated, name))
    _clear_cached_values(data)


def _clear_cached_values(data: BaseModel) -> None:
    fields = type(data).model_fields
    for key in tuple(data.__dict__):
        if key not in fields:
            data.__dict__.pop(key, None)


def _parse_entry_value(raw: str, annotation: Any, old_value: Any) -> Any:
    if raw == '':
        return None
    if isinstance(old_value, list | dict) or _expects_json(annotation):
        return json.loads(raw)
    return raw


def _entry_width(name: str, annotation: Any) -> int | None:
    types = set(_annotation_types(annotation))
    if str in types:
        return None
    if int in types and float not in types and bool not in types:
        return 4 * ENTRY_CHAR_WIDTH
    if float in types:
        return (4 if name in SMALL_FLOAT_FIELDS else 6) * ENTRY_CHAR_WIDTH
    return None


def _annotation_types(annotation: Any) -> tuple[Any, ...]:
    value = getattr(annotation, '__value__', annotation)
    return (value, *_flatten_type_args(value))


def _expects_json(annotation: Any) -> bool:
    args = _flatten_type_args(annotation)
    if str in args:
        return False
    origins = {get_origin(i) or i for i in (annotation, *args)}
    return bool(origins & {list, dict})


def _enum_class(annotation: Any, value: Any) -> type[enum.Enum] | None:
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation
    if isinstance(value, enum.Enum):
        return type(value)

    for arg in _flatten_type_args(annotation):
        if isinstance(arg, type) and issubclass(arg, enum.Enum):
            return arg
    return None


def _flatten_type_args(annotation: Any) -> tuple[Any, ...]:
    origin = get_origin(annotation)
    if origin is None:
        return ()

    args = get_args(annotation)
    return args + tuple(i for a in args for i in _flatten_type_args(a))


class _DemoWaveform(enum.Enum):
    sine = enum.auto()
    triangle = enum.auto()
    sawtooth = enum.auto()


class _DemoSettings(BaseModel):
    waveform: _DemoWaveform = _DemoWaveform.triangle
    gain: float = 0.75
    note_offset: int = 32
    enabled: bool = True
    label: str = 'demo'
    device: str | None = None


def _demo() -> None:
    data = _DemoSettings()
    root = ctk.CTk()
    root.title('Control Panel Demo')

    demo_frame = ctk.CTkFrame(root)
    demo_frame.pack(fill='both', expand=True)

    panel = make_control_panel(demo_frame, data)
    panel.pack(fill='both', expand=True, padx=8, pady=8)

    output = ctk.CTkTextbox(demo_frame, height=120, width=384)
    output.pack(fill='both', expand=False, padx=8, pady=(0, 8))

    def refresh() -> None:
        output.configure(state='normal')
        output.delete('1.0', 'end')
        output.insert('end', data.model_dump_json(indent=2))
        output.configure(state='disabled')
        root.after(100, refresh)

    refresh()
    root.mainloop()


if __name__ == '__main__':
    _demo()
