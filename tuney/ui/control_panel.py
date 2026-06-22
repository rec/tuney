from __future__ import annotations

import enum
import json
import math
from collections.abc import Callable
from typing import Any, TypeAlias, cast, get_args, get_origin

from pydantic import BaseModel, ValidationError
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from tyro._fields import field_list_from_type_or_callable

from ..audio.device import Device
from ..mapper.mapper import Mapper
from ..scale.scale import Scale
from . import constants
from .tooltip import Tooltip

Scalar: TypeAlias = bool | float | int | str | None

CONTROL_FIELD_NAMES: dict[int, str] = {}
INVALID_SCALE_WIDGET_TEXT_COLORS: dict[int, tuple[QLineEdit, str]] = {}


class _OptionControl:
    def __init__(
        self,
        menu: QComboBox,
        data: BaseModel,
        name: str,
        values: Callable[[], list[str]],
    ) -> None:
        self.menu = menu
        self.data = data
        self.name = name
        self.values = values

    def refresh(self) -> None:
        value = _option_text(getattr(self.data, self.name))
        self.menu.clear()
        self.menu.addItems(_option_values(self.values))
        self.menu.setCurrentText(value)


class ControlPanel(QScrollArea):
    def __init__(self, parent: QWidget, data: BaseModel, height: int = 200) -> None:
        super().__init__(parent)
        self.data = data
        self.option_controls: list[_OptionControl] = []
        self.setWidgetResizable(True)
        self.setFixedHeight(height)
        self.content = QWidget()
        self.content.setObjectName('control_panel_content')
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(6)
        self.setWidget(self.content)
        self.rebuild()

    def rebuild(self) -> None:
        _clear_layout(self.content_layout)
        self.option_controls.clear()
        if type(self.data).__name__ == 'Tuney':
            _add_general_controls(self.content, self.data, self.option_controls)
        _add_model_controls(self.content, self.data, self.option_controls)


def _add_model_controls(
    parent: QWidget,
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
        section = QFrame(parent)
        section.setFrameShape(QFrame.Shape.StyledPanel)
        _parent_layout(parent).addWidget(section)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        _add_model_controls(section, child, option_controls, name)


def _add_general_controls(
    parent: QWidget,
    data: BaseModel,
    option_controls: list[_OptionControl],
) -> None:
    controls = _general_controls(data)
    if not controls:
        return
    section = QFrame(parent)
    section.setFrameShape(QFrame.Shape.StyledPanel)
    _parent_layout(parent).addWidget(section)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(2)
    _add_section_title(section, 'general')
    _add_control_group_grid(section, controls, option_controls)


def _add_section_title(parent: QWidget, title: str) -> None:
    label = QLabel(title, parent)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    _parent_layout(parent).addWidget(label)


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
    parent: QWidget,
    controls: list[tuple[BaseModel, str]],
    option_controls: list[_OptionControl],
) -> None:
    frame = QWidget(parent)
    layout = QGridLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(4)
    for column, (data, name) in enumerate(controls):
        _add_control_cell(frame, data, name, option_controls, 0, column, 1)
    _parent_layout(parent).addWidget(frame)


def _add_control_grid(
    parent: QWidget,
    data: BaseModel,
    fields: list[str],
    option_controls: list[_OptionControl],
) -> None:
    frame = QWidget(parent)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    for row_fields in _control_rows(data, fields):
        row_frame = QWidget(frame)
        row_layout = QGridLayout(row_frame)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setHorizontalSpacing(4)
        columns = max(1, len(row_fields))
        for column, name in enumerate(row_fields):
            columnspan = columns + 1 if len(row_fields) == 1 else 1
            _add_control_cell(
                row_frame, data, name, option_controls, 0, column, columnspan
            )
        layout.addWidget(row_frame)
    _parent_layout(parent).addWidget(frame)


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
    parent: QWidget,
    data: BaseModel,
    name: str,
    option_controls: list[_OptionControl],
    row: int,
    column: int,
    columnspan: int,
) -> None:
    cell = QFrame(parent)
    cell.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(cell)
    layout.setContentsMargins(3, 2, 3, 2)
    layout.setSpacing(0)
    cast(QGridLayout, parent.layout()).addWidget(cell, row, column, 1, columnspan)

    _add_control(cell, data, name, option_controls)
    _add_field_tooltips(cell, type(data), name)
    CONTROL_FIELD_NAMES[id(cell)] = name
    if (
        type(data).__name__ == 'MIDI'
        and name != 'enable'
        and not _is_midi_enabled(data)
    ):
        _set_widget_state(cell, False)


def _visible_field_names(data: BaseModel) -> tuple[str, ...]:
    cls = type(data)
    config = constants.CONTROL_CONFIGS.get(cls.__name__)
    hidden = config.hidden_fields + config.general_fields if config else []
    return tuple(
        name
        for name in cls.model_fields
        if name not in hidden and not _is_suppressed_field(cls, name)
    )


def _add_field_tooltips(parent: QWidget, model: type[BaseModel], name: str) -> None:
    control_panel = _control_panel(parent)
    for widget in _field_widgets(parent):
        if isinstance(widget, QWidget):
            Tooltip(
                widget,
                _field_hover_text(model, name),
                lambda: float(getattr(control_panel.data, 'hover_time', 1.0)),
            )


def _field_widgets(parent: Any) -> list[Any]:
    if hasattr(parent, 'winfo_children'):
        children = parent.winfo_children()
    elif isinstance(parent, QWidget):
        children = [
            child
            for child in parent.findChildren(QWidget, options=cast(Any, 0))
            if child.parent() is parent
        ]
    else:
        children = []
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
    parent: QWidget,
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
    parent: QWidget,
    data: BaseModel,
    name: str,
    value: Scalar,
    values: Callable[[], list[str]],
    option_controls: list[_OptionControl],
) -> None:
    frame = QWidget(parent)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(QLabel(name, frame))
    menu = QComboBox(frame)
    width = _entry_width(
        name, type(data).model_fields[name].annotation, type(data).__name__
    )
    if width:
        menu.setFixedWidth(width)
    menu.addItems(_option_values(values))
    menu.setCurrentText(_option_text(value))

    def command(raw: str) -> None:
        if type(data).__name__ == 'Tuney' and name == 'preset' and raw:
            _record_undo(parent)
            cast(Any, data).apply_preset(raw)
            _after(parent, 0, _rebuild_parent_control_panel, parent)
            _after(parent, 0, _rebuild_note_grid, parent)
        else:
            _set_model_value(data, name, raw or None, parent)
            _rebuild_note_grid_if_mapping_changed(parent, data)

    menu.currentTextChanged.connect(command)
    layout.addWidget(menu)
    _parent_layout(parent).addWidget(frame)
    option_controls.append(_OptionControl(menu, data, name, values))


def _control_panel(parent: Any) -> ControlPanel:
    control_panel: Any = parent
    while not isinstance(control_panel, ControlPanel):
        next_parent = (
            control_panel.parent()
            if hasattr(control_panel, 'parent')
            else getattr(control_panel, 'master', None)
        )
        if next_parent is None:
            raise RuntimeError('control panel not found')
        control_panel = next_parent
    return control_panel


def rebuild_control_panel(control_panel: ControlPanel) -> None:
    control_panel.rebuild()


def _rebuild_parent_control_panel(parent: QWidget) -> None:
    rebuild_control_panel(_control_panel(parent))


def _rebuild_note_grid_if_mapping_changed(parent: Any, data: BaseModel) -> None:
    if isinstance(data, Scale | Mapper):
        _after(parent, 0, _rebuild_note_grid, parent)


def _rebuild_note_grid(parent: Any) -> None:
    layout = cast(Any, _control_panel(parent).data).app.ui
    layout.rebuild_note_grid()


def _add_bool_control(parent: QWidget, data: BaseModel, name: str, value: bool) -> None:
    check = QCheckBox(name, parent)
    check.setChecked(value)

    def command(checked: bool) -> None:
        _set_model_value(data, name, checked, parent)
        _rebuild_note_grid_if_mapping_changed(parent, data)
        if type(data).__name__ == 'MIDI' and name == 'enable':
            _set_midi_controls_state(parent, checked)

    check.toggled.connect(command)
    _parent_layout(parent).addWidget(check)


def _set_midi_controls_state(parent: QWidget, enabled: bool) -> None:
    row_frame = parent.parent()
    if row_frame is None:
        return
    for cell in row_frame.findChildren(QFrame, options=cast(Any, 0)):
        if cell.parent() is row_frame and CONTROL_FIELD_NAMES.get(id(cell)) != 'enable':
            _set_widget_state(cell, enabled)


def _set_widget_state(widget: QWidget, enabled: bool) -> None:
    widget.setEnabled(enabled)
    for child in widget.findChildren(QWidget):
        child.setEnabled(enabled)


def _add_entry_control(
    parent: QWidget, data: BaseModel, name: str, value: object
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

    frame = QWidget(parent)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(QLabel(name, frame))
    entry = QLineEdit(text, frame)
    width = _entry_width(name, annotation, type(data).__name__)
    if width:
        entry.setFixedWidth(width)
    text_color = entry.palette().text().color().name()

    def update() -> None:
        raw = entry.text()
        try:
            _set_model_value(
                data, name, _parse_entry_value(raw, annotation, value, name), parent
            )
        except ValidationError:
            _set_invalid_scale_widget(entry, text_color)
            return
        except (TypeError, ValueError, json.JSONDecodeError):
            _set_invalid_scale_widget(entry, text_color)
        else:
            if _set_mapping_entry_state(parent, data, name, entry, text_color):
                return
            entry.setStyleSheet('')

    entry.editingFinished.connect(update)
    layout.addWidget(entry)
    if not width:
        layout.setStretchFactor(entry, 1)
    _parent_layout(parent).addWidget(frame)


def _add_enum_control(
    parent: QWidget,
    data: BaseModel,
    name: str,
    value: enum.Enum,
    enum_cls: type[enum.Enum],
) -> None:
    members = tuple(enum_cls)
    index = members.index(value) if isinstance(value, enum_cls) else 0
    frame = QWidget(parent)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2 if name in {'accidentals', 'limiter'} else 6)
    layout.addWidget(QLabel(name, frame))

    def command(member: enum.Enum) -> None:
        _set_model_value(data, name, member, parent)
        _rebuild_note_grid_if_mapping_changed(parent, data)

    for i, member in enumerate(members):
        radio = QRadioButton(member.name, frame)
        radio.setChecked(i == index)
        radio.toggled.connect(
            lambda checked, member=member: checked and command(member)
        )
        layout.addWidget(radio)
    _parent_layout(parent).addWidget(frame)


def _compact_radio_width(text: str) -> int:
    return constants.RADIO_SIZE + 8 + len(text) * 7


def _set_model_value(
    data: BaseModel, name: str, value: object, parent: Any | None = None
) -> None:
    values = data.model_dump()
    values[name] = value
    validated = type(data).model_validate(values)
    if parent is not None and getattr(data, name) != getattr(validated, name):
        _record_undo(parent)
    object.__setattr__(data, name, getattr(validated, name))
    _clear_cached_values(data)
    if isinstance(data, Device):
        data.notify_change()


def _record_undo(parent: Any) -> None:
    root = _control_panel(parent).data
    if type(root).__name__ == 'Tuney':
        cast(Any, root).app.record_undo()


def _clear_cached_values(data: BaseModel) -> None:
    fields = type(data).model_fields
    for key in tuple(data.__dict__):
        if key not in fields:
            data.__dict__.pop(key, None)


def _set_mapping_entry_state(
    parent: Any, data: BaseModel, name: str, entry: QLineEdit, text_color: str
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


def _set_invalid_scale_widget(widget: QLineEdit, text_color: str) -> None:
    INVALID_SCALE_WIDGET_TEXT_COLORS.setdefault(id(widget), (widget, text_color))
    widget.setStyleSheet('color: red;')


def _clear_invalid_scale_widgets() -> None:
    for widget_id, (widget, _) in tuple(INVALID_SCALE_WIDGET_TEXT_COLORS.items()):
        widget.setStyleSheet('')
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


def _parent_layout(parent: QWidget) -> QVBoxLayout | QGridLayout:
    layout = parent.layout()
    if layout is None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
    return cast(QVBoxLayout | QGridLayout, layout)


def _clear_layout(layout: QVBoxLayout | QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(cast(QVBoxLayout | QGridLayout, child_layout))


def _after(
    parent: Any, delay: int, callback: Callable[..., object], *args: object
) -> None:
    if hasattr(parent, 'after'):
        parent.after(delay, callback, *args)
    else:
        QTimer.singleShot(delay, lambda: callback(*args))


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
