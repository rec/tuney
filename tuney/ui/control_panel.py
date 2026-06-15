from __future__ import annotations

import enum
import math
from typing import Any, get_args, get_origin

import customtkinter as ctk
from pydantic import BaseModel, ValidationError


def make_control_panel(parent: ctk.CTkFrame, data: BaseModel) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(parent)
    fields = tuple(type(data).model_fields)
    columns = max(1, math.ceil(len(fields) ** 0.5))

    for i, name in enumerate(fields):
        row, column = divmod(i, columns)
        cell = ctk.CTkFrame(frame, border_width=1)
        cell.grid(row=row, column=column, padx=4, pady=4, sticky='nsew')
        frame.grid_columnconfigure(column, weight=1)
        frame.grid_rowconfigure(row, weight=1)

        label = ctk.CTkLabel(cell, text=name)
        label.pack(anchor='w')
        _add_control(cell, data, name)

    return frame


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

    ctk.CTkCheckBox(parent, text='', variable=var, command=command).pack(anchor='w')


def _add_entry_control(
    parent: ctk.CTkFrame, data: BaseModel, name: str, value: Any
) -> None:
    var = ctk.StringVar(parent, '' if value is None else str(value))
    entry = ctk.CTkEntry(parent, textvariable=var)
    text_color = entry.cget('text_color')

    def update(*_: Any) -> None:
        raw = var.get()
        try:
            _set_model_value(data, name, None if raw == '' else raw)
        except ValidationError:
            entry.configure(text_color='red')
        else:
            entry.configure(text_color=text_color)

    entry.bind('<FocusOut>', update)
    entry.bind('<Return>', update)
    entry.pack(fill='x')


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

    for i, member in enumerate(members):
        ctk.CTkRadioButton(
            parent,
            text=member.name,
            variable=var,
            value=i,
            command=command,
        ).pack(anchor='w')


def _set_model_value(data: BaseModel, name: str, value: Any) -> None:
    values = data.model_dump()
    values[name] = value
    validated = type(data).model_validate(values)
    object.__setattr__(data, name, getattr(validated, name))


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
