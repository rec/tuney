from __future__ import annotations

import enum
import json
import math
from tkinter import TclError
from typing import Any, get_args, get_origin

import customtkinter as ctk
from customtkinter import CTkFrame
from pydantic import BaseModel, ValidationError

from ..audio.device import dtype_names, output_device_names
from ..audio.midi import output_names as midi_output_names

FONT = 'Arial', 12
TITLE_FONT = 'Arial', 13, 'bold'
CHECKBOX_SIZE = 14
RADIO_SIZE = 14
TOGGLE_HEIGHT = 18
ENTRY_CHAR_WIDTH = 10
SMALL_FLOAT_FIELDS = {'max_gap', 'gain', 'scale'}
GUI_HIDDEN_FIELDS = {'Tuney': {'config_file', 'text', 'disable_gui'}}
GENERAL_HIDDEN_FIELDS = {
    'Tuney': {'max_gap', 'disable_sound', 'run_in_background'},
    'MultiPlayer': {'gain', 'note_offset'},
    'PitchToFrequency': {'function'},
}
CONTROL_ROWS = {
    'Device': [['samplerate', 'device', 'dtype']],
    'Mapper': [['alphabet'], ['length', 'offset', 'case_sensitive', 'invert']],
    'Oscillator': [['waveform', 'period', 'duty_cycle']],
    'Scale': [
        ['alphabet', 'root', 'begin', 'end', 'offset'],
        ['notes', 'intervals'],
    ],
    'TuningImpl': [
        [
            'detune',
            'limit',
            'notes_per_octave',
            'octave_ratio',
            'root_frequency',
            'root_note',
            'table_blend',
        ],
        ['table'],
    ],
    'MIDI': [['enable', 'output', 'channel', 'velocity', 'note_offset']],
    'TextTimings': [
        ['space', 'period', 'comma', 'colon', 'semicolon', 'blank_line'],
        ['overlap', 'seed', 'alpha_only', 'strip_accents', 'scale'],
        ['other', 'timings'],
    ],
}
ENTRY_WIDTHS = {
    'Device.samplerate': 6,
    'MIDI.output': 12,
    'Scale.root': 1,
    'Scale.begin': 1,
    'Scale.end': 1,
    'TextTimings.space': 5,
    'TextTimings.period': 5,
    'TextTimings.comma': 5,
    'TextTimings.colon': 5,
    'TextTimings.semicolon': 5,
    'TextTimings.blank_line': 5,
}
OPTION_VALUES = {
    'Device.device': output_device_names,
    'Device.dtype': dtype_names,
    'MIDI.output': midi_output_names,
}
CONTROL_FIELD_NAMES: dict[int, str] = {}
CONTROL_FG_COLORS: dict[int, Any] = {}
WIDGET_TEXT_COLORS: dict[int, Any] = {}
DISABLED_CONTROL_FG_COLOR = 'gray88', 'gray42'
DISABLED_TEXT_COLOR = 'gray96', 'gray96'


class _OptionControl:
    def __init__(
        self,
        menu: ctk.CTkOptionMenu,
        data: BaseModel,
        name: str,
        values: Any,
    ) -> None:
        self.menu = menu
        self.data = data
        self.name = name
        self.values = values

    def refresh(self) -> None:
        values = _option_values(self.values)
        self.menu.configure(values=values)
        value = _option_text(getattr(self.data, self.name))
        if value:
            self.menu.set(value)


class ControlPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent: CTkFrame, data: BaseModel, height: int = 200) -> None:
        super().__init__(parent, height=height)
        self.option_controls: list[_OptionControl] = []
        if type(data).__name__ == 'Tuney':
            _add_general_controls(self, data, self.option_controls)
        _add_model_controls(self, data, self.option_controls)

    def refresh_devices(self) -> None:
        for option_control in self.option_controls:
            option_control.refresh()


def _add_model_controls(
    parent: CTkFrame | ctk.CTkScrollableFrame,
    data: BaseModel,
    option_controls: list[_OptionControl],
    title: str | None = None,
) -> None:
    if title:
        _add_section_title(parent, title)

    controls = _visible_control_names(data)
    children = _visible_child_names(data)

    if controls:
        _add_control_grid(parent, data, controls, option_controls)

    for name in children:
        child = getattr(data, name)
        assert isinstance(child, BaseModel)
        if not _has_visible_fields(child):
            continue
        if not _visible_control_names(child):
            _add_model_controls(parent, child, option_controls)
            continue
        section = ctk.CTkFrame(parent)
        section.pack(fill='x', expand=True, pady=(6, 0))
        _add_model_controls(section, child, option_controls, name)


def _add_general_controls(
    parent: CTkFrame | ctk.CTkScrollableFrame,
    data: BaseModel,
    option_controls: list[_OptionControl],
) -> None:
    controls = _general_controls(data)
    if not controls:
        return
    section = ctk.CTkFrame(parent)
    section.pack(fill='x', expand=True, pady=(0, 0))
    _add_section_title(section, 'general')
    _add_control_group_grid(section, controls, option_controls)


def _add_section_title(parent: CTkFrame | ctk.CTkScrollableFrame, title: str) -> None:
    title_frame = ctk.CTkFrame(parent, corner_radius=0)
    title_frame.pack(fill='x', pady=(0, 2))
    ctk.CTkLabel(title_frame, text=title, font=TITLE_FONT).pack(
        anchor='w',
        padx=4,
        pady=(2, 2),
    )


def _general_controls(data: Any) -> list[tuple[BaseModel, str]]:
    return [
        (data, 'max_gap'),
        (data, 'disable_sound'),
        (data, 'run_in_background'),
        (data.player, 'gain'),
        (data.player, 'note_offset'),
        (data.player.scale.tuning.pitch_to_frequency, 'function'),
    ]


def _add_control_group_grid(
    parent: CTkFrame | ctk.CTkScrollableFrame,
    controls: list[tuple[BaseModel, str]],
    option_controls: list[_OptionControl],
) -> None:
    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(fill='x', expand=True)
    row_frame = ctk.CTkFrame(frame, fg_color='transparent')
    row_frame.pack(fill='x', expand=True)
    for column in range(len(controls)):
        row_frame.grid_columnconfigure(column, weight=0)
    row_frame.grid_columnconfigure(len(controls), weight=1)

    for column, (data, name) in enumerate(controls):
        _add_control_cell(row_frame, data, name, option_controls, 0, column, 1)


def _add_control_grid(
    parent: CTkFrame | ctk.CTkScrollableFrame,
    data: BaseModel,
    fields: list[str],
    option_controls: list[_OptionControl],
) -> None:
    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(fill='x', expand=True)

    for row_fields in _control_rows(data, fields):
        row_frame = ctk.CTkFrame(frame, fg_color='transparent')
        row_frame.pack(fill='x', expand=True)
        columns = max(1, len(row_fields))
        for column in range(columns):
            row_frame.grid_columnconfigure(column, weight=0)
        row_frame.grid_columnconfigure(columns, weight=1)

        for column, name in enumerate(row_fields):
            columnspan = columns + 1 if len(row_fields) == 1 else 1
            _add_control_cell(
                row_frame, data, name, option_controls, 0, column, columnspan
            )


def _control_rows(data: BaseModel, fields: list[str]) -> list[list[str]]:
    configured = CONTROL_ROWS.get(type(data).__name__)
    if configured is None:
        return _grid_rows(fields)

    used: set[str] = set()
    rows: list[list[str]] = []
    for configured_row in configured:
        if row := [name for name in configured_row if name in fields]:
            rows.append(row)
            used.update(row)

    extra_fields = [name for name in fields if name not in used]
    rows.extend(_grid_rows(extra_fields))
    return rows


def _grid_rows(fields: list[str]) -> list[list[str]]:
    columns = max(1, math.ceil(len(fields) ** 0.5))
    return [fields[i : i + columns] for i in range(0, len(fields), columns)]


def _add_control_cell(
    parent: CTkFrame,
    data: BaseModel,
    name: str,
    option_controls: list[_OptionControl],
    row: int,
    column: int,
    columnspan: int,
) -> None:
    is_bool = isinstance(getattr(data, name), bool)
    cell = ctk.CTkFrame(parent, border_width=1)
    cell.grid(
        row=row,
        column=column,
        columnspan=columnspan,
        padx=2 if is_bool else 4,
        pady=2 if is_bool else 4,
        sticky='w' if is_bool else 'nsew',
    )

    _add_control(cell, data, name, option_controls)
    CONTROL_FIELD_NAMES[id(cell)] = name
    if (
        type(data).__name__ == 'MIDI'
        and name != 'enable'
        and not _is_midi_enabled(data)
    ):
        _set_widget_state(cell, 'disabled')


def _visible_field_names(data: BaseModel) -> tuple[str, ...]:
    cls = type(data)
    hidden = GUI_HIDDEN_FIELDS.get(cls.__name__, set()) | GENERAL_HIDDEN_FIELDS.get(
        cls.__name__, set()
    )
    return tuple(
        name
        for name in cls.model_fields
        if name not in hidden and not _is_suppressed_field(cls, name)
    )


def _visible_control_names(data: BaseModel) -> list[str]:
    return [
        name
        for name in _visible_field_names(data)
        if not isinstance(getattr(data, name), BaseModel)
    ]


def _visible_child_names(data: BaseModel) -> list[str]:
    return [
        name
        for name in _visible_field_names(data)
        if isinstance(getattr(data, name), BaseModel)
    ]


def _has_visible_fields(data: BaseModel) -> bool:
    return bool(
        _visible_control_names(data)
        or any(
            _has_visible_fields(getattr(data, name))
            for name in _visible_child_names(data)
        )
    )


def _is_midi_enabled(data: Any) -> bool:
    return bool(data.enable)


def _is_suppressed_field(cls: type[BaseModel], name: str) -> bool:
    annotation = cls.__annotations__.get(name, '')
    return str(annotation).startswith('tyro.conf.Suppress') or 'Suppress' in {
        str(i) for i in get_args(annotation)
    }


def _option_values(values: Any) -> list[str]:
    return ['', *values()]


def _option_text(value: Any) -> str:
    return '' if value is None else str(value)


def _add_control(
    parent: CTkFrame,
    data: BaseModel,
    name: str,
    option_controls: list[_OptionControl],
) -> None:
    value = getattr(data, name)
    annotation = type(data).model_fields[name].annotation
    enum_cls = _enum_class(annotation, value)

    if values := OPTION_VALUES.get(f'{type(data).__name__}.{name}'):
        _add_option_control(parent, data, name, value, values, option_controls)
    elif enum_cls:
        _add_enum_control(parent, data, name, value, enum_cls)
    elif isinstance(value, bool):
        _add_bool_control(parent, data, name, value)
    else:
        _add_entry_control(parent, data, name, value)


def _add_option_control(
    parent: CTkFrame,
    data: BaseModel,
    name: str,
    value: Any,
    values: Any,
    option_controls: list[_OptionControl],
) -> None:
    string_var = ctk.StringVar(parent, _option_text(value))

    def command(raw: str) -> None:
        _set_model_value(data, name, raw or None)

    annotation = type(data).model_fields[name].annotation
    width = _entry_width(name, annotation, type(data).__name__)
    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(fill='x')
    ctk.CTkLabel(frame, text=name, font=FONT).pack(side='left', padx=(0, 4))
    menu = (
        ctk.CTkOptionMenu(
            frame,
            width=width,
            values=_option_values(values),
            variable=string_var,
            command=command,
            font=FONT,
        )
        if width
        else ctk.CTkOptionMenu(
            frame,
            values=_option_values(values),
            variable=string_var,
            command=command,
            font=FONT,
        )
    )
    menu.pack(side='left')
    option_controls.append(_OptionControl(menu, data, name, values))


def _add_bool_control(
    parent: CTkFrame, data: BaseModel, name: str, value: bool
) -> None:
    var = ctk.IntVar(parent, int(value))

    def command() -> None:
        _set_model_value(data, name, bool(var.get()))
        if type(data).__name__ == 'MIDI' and name == 'enable':
            _set_midi_controls_state(parent, bool(var.get()))

    ctk.CTkCheckBox(
        parent,
        width=0,
        text=name,
        variable=var,
        command=command,
        font=FONT,
        height=TOGGLE_HEIGHT,
        checkbox_width=CHECKBOX_SIZE,
        checkbox_height=CHECKBOX_SIZE,
    ).pack(anchor='w')


def _set_midi_controls_state(parent: CTkFrame, enabled: bool) -> None:
    row_frame = parent.master
    if row_frame is None:
        return
    for cell in row_frame.winfo_children():
        if CONTROL_FIELD_NAMES.get(id(cell)) != 'enable':
            _set_widget_state(cell, 'normal' if enabled else 'disabled')


def _set_widget_state(widget: Any, state: str) -> None:
    try:
        widget.configure(state=state)
    except (TclError, ValueError):
        pass
    _set_widget_text_color(widget, state)
    _set_control_fg_color(widget, state)
    for child in widget.winfo_children():
        _set_widget_state(child, state)


def _set_widget_text_color(widget: Any, state: str) -> None:
    try:
        text_color = widget.cget('text_color')
    except (AttributeError, TclError, ValueError):
        return

    if state == 'disabled':
        WIDGET_TEXT_COLORS.setdefault(id(widget), text_color)
        try:
            widget.configure(text_color=DISABLED_TEXT_COLOR)
        except (TclError, ValueError):
            pass
        return

    if id(widget) in WIDGET_TEXT_COLORS:
        try:
            widget.configure(text_color=WIDGET_TEXT_COLORS.pop(id(widget)))
        except (TclError, ValueError):
            pass


def _set_control_fg_color(widget: Any, state: str) -> None:
    if id(widget) not in CONTROL_FIELD_NAMES:
        return

    if state == 'disabled':
        try:
            CONTROL_FG_COLORS.setdefault(id(widget), widget.cget('fg_color'))
            widget.configure(fg_color=DISABLED_CONTROL_FG_COLOR)
        except (AttributeError, TclError, ValueError):
            pass
        return

    if id(widget) in CONTROL_FG_COLORS:
        try:
            widget.configure(fg_color=CONTROL_FG_COLORS.pop(id(widget)))
        except (TclError, ValueError):
            pass


def _add_entry_control(
    parent: CTkFrame, data: BaseModel, name: str, value: Any
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
    width = _entry_width(name, annotation, type(data).__name__)
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
    parent: CTkFrame,
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
    radio_pad = 3 if name in {'dtype', 'waveform', 'function'} else 6
    radio_width = (
        70 if name in {'waveform', 'function'} else 50 if name == 'dtype' else 100
    )
    for i, member in enumerate(members):
        ctk.CTkRadioButton(
            frame,
            width=radio_width,
            text=member.name,
            variable=var,
            value=i,
            command=command,
            font=FONT,
            height=TOGGLE_HEIGHT,
            radiobutton_width=RADIO_SIZE,
            radiobutton_height=RADIO_SIZE,
        ).pack(side='left', padx=(0, radio_pad))


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


def _entry_width(
    name: str, annotation: Any, model_name: str | None = None
) -> int | None:
    if model_name and (characters := ENTRY_WIDTHS.get(f'{model_name}.{name}')):
        return characters * ENTRY_CHAR_WIDTH

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

    panel = ControlPanel(demo_frame, data)
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
