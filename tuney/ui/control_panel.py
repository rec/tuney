from __future__ import annotations

import enum
import json
import math
from collections.abc import Callable
from tkinter import Misc, TclError
from typing import Any, TypeAlias, cast, get_args, get_origin

import customtkinter as ctk
from customtkinter import CTkFrame
from pydantic import BaseModel, ValidationError
from tyro._fields import field_list_from_type_or_callable

from ..audio.device import Device
from ..mapper.mapper import Mapper
from ..scale.scale import Scale
from . import constants
from .tooltip import Tooltip

Scalar: TypeAlias = bool | float | int | str | None

CONTROL_FIELD_NAMES: dict[int, str] = {}
CONTROL_FG_COLORS: dict[int, Any] = {}
WIDGET_TEXT_COLORS: dict[int, Any] = {}
INVALID_SCALE_WIDGET_TEXT_COLORS: dict[int, tuple[Any, Any]] = {}


class _OptionControl:
    def __init__(
        self,
        menu: ctk.CTkOptionMenu,
        data: BaseModel,
        name: str,
        values: Callable[[], list[str]],
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
        self.data = data
        self.option_controls: list[_OptionControl] = []
        if type(data).__name__ == 'Tuney':
            _add_general_controls(self, data, self.option_controls)
        _add_model_controls(self, data, self.option_controls)
        _bind_textbox_focus(self, include_root=True)


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
    ctk.CTkLabel(title_frame, text=title, font=constants.TITLE_FONT).pack(
        anchor='w',
        padx=4,
        pady=(2, 2),
    )


def _general_controls(data: Any) -> list[tuple[BaseModel, str]]:
    return [
        (data, 'preset'),
        (data, 'max_gap'),
        (data, 'hover_time'),
        (data, 'silent'),
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
    config = constants.CONTROL_CONFIGS.get(type(data).__name__)
    if config is None or not config.rows:
        return _grid_rows(fields)

    used: set[str] = set()
    rows: list[list[str]] = []
    for configured_row in config.rows:
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
    _add_field_tooltips(cell, type(data), name)
    CONTROL_FIELD_NAMES[id(cell)] = name
    if (
        type(data).__name__ == 'MIDI'
        and name != 'enable'
        and not _is_midi_enabled(data)
    ):
        _set_widget_state(cell, 'disabled')


def _visible_field_names(data: BaseModel) -> tuple[str, ...]:
    cls = type(data)
    config = constants.CONTROL_CONFIGS.get(cls.__name__)
    hidden = config.hidden_fields + config.general_fields if config else []
    return tuple(
        name
        for name in cls.model_fields
        if name not in hidden and not _is_suppressed_field(cls, name)
    )


def _add_field_tooltips(parent: CTkFrame, model: type[BaseModel], name: str) -> None:
    control_panel = _control_panel(parent)
    for widget in _field_widgets(parent):
        Tooltip(
            widget,
            _field_hover_text(model, name),
            lambda: float(getattr(control_panel.data, 'hover_time', 1.0)),
        )


def _field_widgets(parent: Misc) -> list[Misc]:
    children = parent.winfo_children()
    if not children:
        return [parent]
    return [widget for child in children for widget in _field_widgets(child)]


def _field_hover_text(model: type[BaseModel], name: str) -> str:
    return _rewrap_hover_text(_field_help(model, name) or name)


def _rewrap_hover_text(text: str) -> str:
    return '\n\n'.join(' '.join(paragraph.split()) for paragraph in text.split('\n\n'))


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


def _option_values(values: Callable[[], list[str]]) -> list[str]:
    return ['', *values()]


def _option_text(value: Scalar) -> str:
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

    if values := constants.OPTION_VALUES.get(f'{type(data).__name__}.{name}'):
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
    value: Scalar,
    values: Callable[[], list[str]],
    option_controls: list[_OptionControl],
) -> None:
    string_var = ctk.StringVar(parent, _option_text(value))

    def command(raw: str) -> None:
        if type(data).__name__ == 'Tuney' and name == 'preset' and raw:
            cast(Any, data).apply_preset(raw)
            parent.after(0, _rebuild_control_panel, parent)
            parent.after(0, _rebuild_note_grid, parent)
        else:
            _set_model_value(data, name, raw or None)
            _rebuild_note_grid_if_mapping_changed(parent, data)

    annotation = type(data).model_fields[name].annotation
    width = _entry_width(name, annotation, type(data).__name__)
    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(fill='x')
    ctk.CTkLabel(frame, text=name, font=constants.FONT).pack(side='left', padx=(0, 4))
    menu = (
        ctk.CTkOptionMenu(
            frame,
            width=width,
            values=_option_values(values),
            variable=string_var,
            command=command,
            font=constants.FONT,
        )
        if width
        else ctk.CTkOptionMenu(
            frame,
            values=_option_values(values),
            variable=string_var,
            command=command,
            font=constants.FONT,
        )
    )
    menu.pack(side='left')
    option_controls.append(_OptionControl(menu, data, name, values))


def _control_panel(parent: Misc) -> ControlPanel:
    control_panel: Any = parent
    while not isinstance(control_panel, ControlPanel):
        control_panel = control_panel.master
    return control_panel


def _rebuild_control_panel(parent: Misc) -> None:
    control_panel = _control_panel(parent)
    for child in control_panel.winfo_children():
        child.destroy()
    control_panel.option_controls.clear()
    if type(control_panel.data).__name__ == 'Tuney':
        _add_general_controls(
            control_panel, control_panel.data, control_panel.option_controls
        )
    _add_model_controls(
        control_panel, control_panel.data, control_panel.option_controls
    )
    _bind_textbox_focus(control_panel)


def _bind_textbox_focus(
    control_panel: ControlPanel, include_root: bool = False
) -> None:
    widgets = [control_panel] if include_root else []
    widgets.extend(_child_widgets(control_panel))
    for widget in widgets:
        widget.bind(
            '<ButtonRelease-1>',
            lambda event: _focus_textbox_if_not_editable(control_panel, event),
            add='+',
        )


def _child_widgets(widget: Misc) -> list[Misc]:
    children = list(widget.winfo_children())
    return children + [i for child in children for i in _child_widgets(child)]


def _focus_textbox_if_not_editable(control_panel: ControlPanel, event: object) -> None:
    widget = cast(Any, event).widget
    if _is_editable_control(control_panel, widget):
        return

    layout = getattr(control_panel.winfo_toplevel(), 'layout', None)
    if layout is None:
        return
    control_panel.after_idle(cast(Any, layout).textbox.focus_set)


def _is_editable_control(control_panel: ControlPanel, widget: Misc) -> bool:
    current: Misc | None = widget
    while current is not control_panel and current is not None:
        if isinstance(current, ctk.CTkEntry | ctk.CTkOptionMenu):
            return True
        current = current.master
    return False


def _rebuild_note_grid_if_mapping_changed(parent: Misc, data: BaseModel) -> None:
    if isinstance(data, Scale | Mapper):
        parent.after(0, _rebuild_note_grid, parent)


def _rebuild_note_grid(parent: Misc) -> None:
    layout = cast(Any, _control_panel(parent).data).app.layout
    layout.rebuild_note_grid()


def _add_bool_control(
    parent: CTkFrame, data: BaseModel, name: str, value: bool
) -> None:
    var = ctk.IntVar(parent, int(value))

    def command() -> None:
        _set_model_value(data, name, bool(var.get()))
        _rebuild_note_grid_if_mapping_changed(parent, data)
        if type(data).__name__ == 'MIDI' and name == 'enable':
            _set_midi_controls_state(parent, bool(var.get()))

    ctk.CTkCheckBox(
        parent,
        width=0,
        text=name,
        variable=var,
        command=command,
        font=constants.FONT,
        height=constants.TOGGLE_HEIGHT,
        checkbox_width=constants.CHECKBOX_SIZE,
        checkbox_height=constants.CHECKBOX_SIZE,
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
            widget.configure(text_color=constants.DISABLED_TEXT_COLOR)
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
            widget.configure(fg_color=constants.DISABLED_CONTROL_FG_COLOR)
        except (AttributeError, TclError, ValueError):
            pass
        return

    if id(widget) in CONTROL_FG_COLORS:
        try:
            widget.configure(fg_color=CONTROL_FG_COLORS.pop(id(widget)))
        except (TclError, ValueError):
            pass


def _add_entry_control(
    parent: CTkFrame, data: BaseModel, name: str, value: object
) -> None:
    annotation = type(data).model_fields[name].annotation
    if name == 'alphabet' and value in (None, '') and hasattr(data, 'alphabet_'):
        value = data.alphabet_
    if isinstance(data, Scale) and name == 'intervals' and isinstance(value, list):
        text = ''.join(str(i) for i in value)
    elif value is None:
        text = ''
    elif isinstance(value, list | dict):
        text = json.dumps(value)
    else:
        text = str(value)
    var = ctk.StringVar(parent, text)
    width = _entry_width(name, annotation, type(data).__name__)
    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(fill='x')
    ctk.CTkLabel(frame, text=name, font=constants.FONT).pack(side='left', padx=(0, 4))
    entry = (
        ctk.CTkEntry(frame, width=width, textvariable=var)
        if width
        else ctk.CTkEntry(frame, textvariable=var)
    )
    text_color = entry.cget('text_color')

    def update(*_: Any) -> None:
        raw = var.get()
        try:
            _set_model_value(
                data, name, _parse_entry_value(raw, annotation, value, name)
            )
        except ValidationError:
            _set_invalid_scale_widget(entry, text_color)
            return
        except (TypeError, ValueError):
            _set_invalid_scale_widget(entry, text_color)
        else:
            if _set_mapping_entry_state(parent, data, name, entry, text_color):
                return
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
        _rebuild_note_grid_if_mapping_changed(parent, data)

    frame = ctk.CTkFrame(parent, fg_color='transparent')
    frame.pack(anchor='w')
    ctk.CTkLabel(frame, text=name, font=constants.FONT).pack(side='left', padx=(0, 4))
    radio_pad = (
        1
        if name in {'accidentals', 'limiter'}
        else 3
        if name in {'dtype', 'waveform', 'function'}
        else 6
    )
    radio_width = (
        70
        if name in {'waveform', 'function'}
        else 50
        if name == 'dtype'
        else 100
    )
    for i, member in enumerate(members):
        compact_radio = name in {'accidentals', 'limiter'}
        ctk.CTkRadioButton(
            frame,
            width=_compact_radio_width(member.name) if compact_radio else radio_width,
            text=member.name,
            variable=var,
            value=i,
            command=command,
            font=constants.FONT,
            height=constants.TOGGLE_HEIGHT,
            radiobutton_width=constants.RADIO_SIZE,
            radiobutton_height=constants.RADIO_SIZE,
        ).pack(side='left', padx=(0, radio_pad))


def _compact_radio_width(text: str) -> int:
    return constants.RADIO_SIZE + 8 + len(text) * 7


def _set_model_value(data: BaseModel, name: str, value: object) -> None:
    values = data.model_dump()
    values[name] = value
    validated = type(data).model_validate(values)
    object.__setattr__(data, name, getattr(validated, name))
    _clear_cached_values(data)
    if isinstance(data, Device):
        data.notify_change()


def _clear_cached_values(data: BaseModel) -> None:
    fields = type(data).model_fields
    for key in tuple(data.__dict__):
        if key not in fields:
            data.__dict__.pop(key, None)


def _set_mapping_entry_state(
    parent: Misc, data: BaseModel, name: str, entry: Any, text_color: Any
) -> bool:
    if isinstance(data, Mapper):
        _rebuild_note_grid_if_mapping_changed(parent, data)
        return False

    if not isinstance(data, Scale):
        return False

    note_errors = _scale_note_errors(data)
    has_note_buttons = _scale_has_note_buttons(data)
    if (name == 'notes' and note_errors) or not has_note_buttons:
        _set_invalid_scale_widget(entry, text_color)
        _rebuild_note_grid_if_mapping_changed(parent, data)
        return True

    if not note_errors:
        _clear_invalid_scale_widgets()
    _rebuild_note_grid_if_mapping_changed(parent, data)
    return False


def _scale_note_errors(scale: Scale) -> list[str]:
    if not scale.notes:
        return []
    _, errors = scale._to_notes(scale.notes)
    return errors


def _scale_has_note_buttons(scale: Scale) -> bool:
    try:
        return scale.note_count > 0
    except (AssertionError, ValueError, ZeroDivisionError):
        return False


def _set_invalid_scale_widget(widget: Any, text_color: Any) -> None:
    INVALID_SCALE_WIDGET_TEXT_COLORS.setdefault(id(widget), (widget, text_color))
    widget.configure(text_color='red')


def _clear_invalid_scale_widgets() -> None:
    for widget_id, (widget, text_color) in tuple(
        INVALID_SCALE_WIDGET_TEXT_COLORS.items()
    ):
        try:
            widget.configure(text_color=text_color)
        except (TclError, ValueError):
            pass
        INVALID_SCALE_WIDGET_TEXT_COLORS.pop(widget_id, None)


def _parse_entry_value(
    raw: str, annotation: Any, old_value: object, name: str = ''
) -> object:
    if raw == '':
        return None
    if name == 'intervals' and isinstance(old_value, list):
        return raw
    if isinstance(old_value, list | dict) or _expects_json(annotation):
        return json.loads(raw)
    return raw


def _entry_width(
    name: str, annotation: Any, model_name: str | None = None
) -> int | None:
    if model_name and (
        characters := constants.ENTRY_WIDTHS.get(f'{model_name}.{name}')
    ):
        return characters * constants.ENTRY_CHAR_WIDTH

    types = set(_annotation_types(annotation))
    if str in types:
        return None
    if int in types and float not in types and bool not in types:
        return 4 * constants.ENTRY_CHAR_WIDTH
    if float in types:
        return (
            4 if name in constants.SMALL_FLOAT_FIELDS else 6
        ) * constants.ENTRY_CHAR_WIDTH
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
