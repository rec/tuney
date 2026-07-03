from __future__ import annotations

import enum
import json
import math
from collections.abc import Callable
from typing import Any, TypeAlias, cast, get_args, get_origin

from pydantic import BaseModel, ValidationError
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDial,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from tyro._fields import field_list_from_type_or_callable

from ..audio.device import Device
from ..audio.polyphony import Polyphony
from ..display import Display
from ..mapper.mapper import Mapper
from ..scale.scale import Scale
from . import constants
from .tooltip import Tooltip

Scalar: TypeAlias = bool | float | int | str | None

CONTROL_FIELD_NAMES: dict[int, str] = {}
INVALID_SCALE_WIDGET_TEXT_COLORS: dict[int, tuple[QLineEdit, str]] = {}
GENERAL_COLUMNS = 4
LABEL_PADDING = 8
MIN_EDITOR_WIDTH = 72
MIN_TEXT_EDITOR_WIDTH = 160
SECTION_STYLE = """
QFrame#control_section {
    background: #f7f7f7;
    border: 1px solid #c8c8c8;
    border-radius: 4px;
}
QLabel#control_section_title {
    color: #303030;
}
"""


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
        self.show_advanced = True
        self.setWidgetResizable(True)
        self.setMinimumHeight(min(height, 80))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content = QWidget()
        self.content.setObjectName('control_panel_content')
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(8)
        self.setWidget(self.content)
        self.rebuild()

    def rebuild(self) -> None:
        _clear_layout(self.content_layout)
        self.option_controls.clear()
        if type(self.data).__name__ == 'Tuney':
            _add_mode_switch(self)
            _add_general_controls(
                self.content,
                self.data,
                self.option_controls,
                self.show_advanced,
            )
        _add_model_controls(
            self.content, self.data, self.option_controls, advanced=self.show_advanced
        )


def _add_mode_switch(control_panel: ControlPanel) -> None:
    frame = QWidget(control_panel.content)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    group = QButtonGroup(frame)
    for label, advanced in [('Beginner', False), ('Advanced', True)]:
        radio = QRadioButton(label, frame)
        radio.setChecked(control_panel.show_advanced == advanced)
        radio.toggled.connect(
            lambda checked, advanced=advanced: checked
            and _set_control_panel_mode(control_panel, advanced)
        )
        group.addButton(radio)
        layout.addWidget(radio)
    layout.addStretch()
    control_panel.content_layout.addWidget(frame)


def _set_control_panel_mode(control_panel: ControlPanel, advanced: bool) -> None:
    control_panel.show_advanced = advanced
    control_panel.rebuild()


def _add_model_controls(
    parent: QWidget,
    data: BaseModel,
    option_controls: list[_OptionControl],
    title: str | None = None,
    advanced: bool = True,
) -> None:
    if title:
        _add_section_title(parent, title)

    controls = _visible_control_names(data, advanced)
    children = [
        name
        for name in _visible_child_names(data, advanced)
        if not _inline_child(getattr(data, name))
    ]

    if controls:
        _add_control_grid(parent, data, controls, option_controls, advanced)

    for name in children:
        child = getattr(data, name)
        assert isinstance(child, BaseModel)
        if not _has_visible_fields(child, advanced):
            continue
        if not _visible_control_names(child, advanced):
            _add_model_controls(parent, child, option_controls, advanced=advanced)
            continue
        section = _section(parent)
        _parent_layout(parent).addWidget(section)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(3)
        _add_model_controls(section, child, option_controls, name, advanced)


def _add_general_controls(
    parent: QWidget,
    data: BaseModel,
    option_controls: list[_OptionControl],
    advanced: bool = True,
) -> None:
    controls = _general_controls(data, advanced)
    if not controls:
        return
    section = _section(parent)
    _parent_layout(parent).addWidget(section)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(6, 4, 6, 6)
    layout.setSpacing(3)
    _add_section_title(section, 'general')
    _add_control_group_grid(section, controls, option_controls)


def _section(parent: QWidget) -> QFrame:
    section = QFrame(parent)
    section.setObjectName('control_section')
    section.setFrameShape(QFrame.Shape.StyledPanel)
    section.setStyleSheet(SECTION_STYLE)
    return section


def _add_section_title(parent: QWidget, title: str) -> None:
    label = QLabel(title, parent)
    label.setObjectName('control_section_title')
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    _parent_layout(parent).addWidget(label)


def _general_controls(data: Any, advanced: bool = True) -> list[tuple[BaseModel, str]]:
    return [
        (model, name)
        for model in _model_tree(data)
        for name in type(model).model_fields
        if _control_metadata(type(model), name).general
        and (advanced or _is_beginner_field(model, name))
    ]


def _add_control_group_grid(
    parent: QWidget,
    controls: list[tuple[BaseModel, str]],
    option_controls: list[_OptionControl],
) -> None:
    frame = QWidget(parent)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)
    for row_controls in _control_groups(controls, GENERAL_COLUMNS):
        row_frame = QWidget(frame)
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        for data, name in row_controls:
            _add_control_cell(row_frame, data, name, option_controls)
        row_layout.addStretch()
        layout.addWidget(row_frame)
    _parent_layout(parent).addWidget(frame)


def _control_groups(
    controls: list[tuple[BaseModel, str]], size: int
) -> list[list[tuple[BaseModel, str]]]:
    return [controls[i : i + size] for i in range(0, len(controls), size)]


def _add_control_grid(
    parent: QWidget,
    data: BaseModel,
    fields: list[str],
    option_controls: list[_OptionControl],
    advanced: bool,
) -> None:
    frame = QWidget(parent)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    for row_fields in _control_ref_rows(_control_refs(data, fields, advanced)):
        row_frame = QWidget(frame)
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        for control_data, name in row_fields:
            _add_control_cell(row_frame, control_data, name, option_controls)
        row_layout.addStretch()
        layout.addWidget(row_frame)
    _parent_layout(parent).addWidget(frame)


def _control_refs(
    data: BaseModel, fields: list[str], advanced: bool
) -> list[tuple[BaseModel, str]]:
    controls = [(data, name) for name in fields]
    for name in _visible_child_names(data, advanced):
        child = getattr(data, name)
        if _inline_child(child):
            controls.extend(
                (child, child_name)
                for child_name in _visible_control_names(child, advanced)
            )
    return controls


def _control_ref_rows(
    controls: list[tuple[BaseModel, str]],
) -> list[list[tuple[BaseModel, str]]]:
    if not any(
        _control_metadata(type(data), name).row is not None for data, name in controls
    ):
        return _control_groups(controls, max(1, math.ceil(len(controls) ** 0.5)))

    rows: list[list[tuple[BaseModel, str]]] = []
    row_numbers = sorted(
        {
            row
            for data, name in controls
            if (row := _control_metadata(type(data), name).row) is not None
        }
    )
    for row_number in row_numbers:
        row = [
            (data, name)
            for data, name in controls
            if _control_metadata(type(data), name).row == row_number
        ]
        rows.append(
            sorted(
                row,
                key=lambda control: _control_metadata(
                    type(control[0]), control[1]
                ).order,
            )
        )

    extra_fields = [
        control
        for control in controls
        if _control_metadata(type(control[0]), control[1]).row is None
    ]
    rows.extend(
        _control_groups(extra_fields, max(1, math.ceil(len(extra_fields) ** 0.5)))
    )
    return rows


def _inline_child(data: object) -> bool:
    return isinstance(data, Polyphony)


def _control_rows(data: BaseModel, fields: list[str]) -> list[list[str]]:
    if not any(_control_metadata(type(data), name).row is not None for name in fields):
        return _grid_rows(fields)

    rows: list[list[str]] = []
    row_numbers = sorted(
        {
            row
            for name in fields
            if (row := _control_metadata(type(data), name).row) is not None
        }
    )
    for row_number in row_numbers:
        row = [
            name
            for name in fields
            if _control_metadata(type(data), name).row == row_number
        ]
        rows.append(
            sorted(
                row,
                key=lambda name: _control_metadata(type(data), name).order,
            )
        )

    extra_fields = [
        name for name in fields if _control_metadata(type(data), name).row is None
    ]
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
) -> None:
    cell = QWidget(parent)
    layout = QVBoxLayout(cell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    if _is_wide_field(data, name):
        cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cast(QHBoxLayout, parent.layout()).addWidget(cell, stretch=1)
    else:
        cell.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        cast(QHBoxLayout, parent.layout()).addWidget(cell)

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
    return tuple(
        name
        for name in cls.model_fields
        if not _is_suppressed_field(cls, name)
        and not _control_metadata(cls, name).hidden
        and not _control_metadata(cls, name).general
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
            for child in parent.findChildren(
                QWidget,
                options=Qt.FindChildOption.FindDirectChildrenOnly,
            )
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


def _visible_control_names(data: BaseModel, advanced: bool = True) -> list[str]:
    return [
        name
        for name in _visible_field_names(data)
        if not isinstance(getattr(data, name), BaseModel)
        and (advanced or _is_beginner_field(data, name))
    ]


def _visible_child_names(data: BaseModel, advanced: bool = True) -> list[str]:
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


def _is_beginner_field(data: BaseModel, name: str) -> bool:
    return _control_metadata(type(data), name).beginner


def _model_tree(data: BaseModel) -> list[BaseModel]:
    models = [data]
    for name in type(data).model_fields:
        if _is_suppressed_field(type(data), name):
            continue
        if _control_metadata(type(data), name).hidden:
            continue
        child = getattr(data, name)
        if isinstance(child, BaseModel):
            models.extend(_model_tree(child))
    return models


def _control_metadata(cls: type[BaseModel], name: str) -> Display:
    for metadata in cls.model_fields[name].metadata:
        if isinstance(metadata, Display):
            return metadata
    return Display()


def _display_label(name: str) -> str:
    return name.replace('_', ' ')


def _add_labeled_control_frame(
    parent: QWidget,
    name: str,
    spacing: int = 4,
) -> tuple[QWidget, QHBoxLayout, QLabel]:
    frame = QWidget(parent)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    label = QLabel(_display_label(name), frame)
    _configure_label(label)
    layout.addWidget(label)
    return frame, layout, label


def _configure_label(label: QLabel) -> None:
    label.setObjectName('control_label')
    width = label.fontMetrics().horizontalAdvance(label.text()) + LABEL_PADDING
    label.setMinimumWidth(width)
    label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)


def _configure_editor(widget: QWidget, width: int | None = None) -> None:
    widget.setObjectName('control_editor')
    minimum = max(width or MIN_TEXT_EDITOR_WIDTH, MIN_EDITOR_WIDTH)
    widget.setMinimumWidth(minimum)
    if width:
        widget.setFixedWidth(minimum)
    else:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def _is_wide_field(data: BaseModel, name: str) -> bool:
    value = getattr(data, name)
    annotation = type(data).model_fields[name].annotation
    display = _control_metadata(type(data), name)
    if display.width:
        return False
    if isinstance(value, bool | int | float | enum.Enum):
        return False
    if display.options:
        return False
    return str in set(_annotation_types(annotation)) or isinstance(value, list | dict)


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
    display = _control_metadata(type(data), name)
    enum_cls = _enum_class(annotation, value)

    if values := display.options:
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
    frame, layout, _ = _add_labeled_control_frame(parent, name)
    menu = QComboBox(frame)
    width = _entry_width(
        name,
        type(data).model_fields[name].annotation,
        _control_metadata(type(data), name),
    )
    _configure_editor(menu, width)
    menu.addItems(_option_values(values))
    menu.setCurrentText(_option_text(value))

    def command(raw: str) -> None:
        if type(data).__name__ == 'Tuney' and name == 'preset' and raw:
            _checkpoint_undo(parent)
            cast(Any, data).state.apply_preset(raw)
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
    layout = cast(Any, _control_panel(parent).data).state.app.ui
    layout.rebuild_note_grid()


def _add_bool_control(parent: QWidget, data: BaseModel, name: str, value: bool) -> None:
    check = QCheckBox(_display_label(name), parent)
    check.setMinimumWidth(check.sizeHint().width())
    check.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
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
    for cell in row_frame.findChildren(
        QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
    ):
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
    if _can_use_spin_control(annotation, value):
        _add_spin_control(parent, data, name, value)
        return
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

    frame, layout, _ = _add_labeled_control_frame(parent, name)
    entry = QLineEdit(text, frame)
    width = _entry_width(name, annotation, _control_metadata(type(data), name))
    _configure_editor(entry, width)
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
    layout.setStretchFactor(entry, 1)
    _parent_layout(parent).addWidget(frame)


def _add_spin_control(
    parent: QWidget, data: BaseModel, name: str, value: object
) -> None:
    annotation = type(data).model_fields[name].annotation
    frame, layout, _ = _add_labeled_control_frame(parent, name)

    if _is_int_annotation(annotation):
        assert isinstance(value, int)
        spin = QSpinBox(frame)
        spin.setRange(-9999, 9999)
        spin.setValue(value)

        def update() -> None:
            _set_model_value(data, name, spin.value(), parent)
            _rebuild_note_grid_if_mapping_changed(parent, data)

        spin.editingFinished.connect(update)
        layout.addWidget(spin)
    else:
        assert isinstance(value, float | int)
        spin = QDoubleSpinBox(frame)
        spin.setDecimals(3)
        spin.setRange(-9999.0, 9999.0)
        spin.setSingleStep(_float_step(data, name))
        spin.setValue(float(value))

        def update() -> None:
            _set_model_value(data, name, spin.value(), parent)
            _rebuild_note_grid_if_mapping_changed(parent, data)

        spin.editingFinished.connect(update)
        layout.addWidget(spin)

        if _uses_dial(data, name):
            dial = QDial(frame)
            dial.setFixedSize(30, 30)
            dial.setWrapping(False)
            dial.setRange(0, 100)
            dial.setValue(_dial_value(spin.value(), name))
            dial.valueChanged.connect(
                lambda value: spin.setValue(_spin_value(value, name))
            )
            dial.sliderReleased.connect(update)
            layout.addWidget(dial)

    width = _entry_width(name, annotation, _control_metadata(type(data), name))
    _configure_editor(spin, max(width + 18, 56) if width else MIN_EDITOR_WIDTH)
    _parent_layout(parent).addWidget(frame)


def _can_use_spin_control(annotation: Any, value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    return isinstance(value, int | float) and (
        _is_int_annotation(annotation) or _is_float_annotation(annotation)
    )


def _is_int_annotation(annotation: Any) -> bool:
    types = set(_annotation_types(annotation))
    return int in types and float not in types and bool not in types


def _is_float_annotation(annotation: Any) -> bool:
    return float in set(_annotation_types(annotation))


def _float_step(data: BaseModel, name: str) -> float:
    return _control_metadata(type(data), name).step


def _uses_dial(data: BaseModel, name: str) -> bool:
    return _control_metadata(type(data), name).dial


def _dial_value(value: float, name: str) -> int:
    minimum, maximum = _dial_range(name)
    return round((float(value) - minimum) * 100 / (maximum - minimum))


def _spin_value(value: int, name: str) -> float:
    minimum, maximum = _dial_range(name)
    return minimum + value * (maximum - minimum) / 100


def _dial_range(name: str) -> tuple[float, float]:
    match name:
        case 'duty_cycle':
            return 0.0, 1.0
        case 'gain':
            return 0.0, 2.0
        case 'minimum_note_time':
            return 0.0, 2.0
        case _:
            return 0.0, 4.0


def _add_enum_control(
    parent: QWidget,
    data: BaseModel,
    name: str,
    value: enum.Enum,
    enum_cls: type[enum.Enum],
) -> None:
    members = tuple(enum_cls)
    index = members.index(value) if isinstance(value, enum_cls) else 0
    frame, layout, _ = _add_labeled_control_frame(
        parent, name, 2 if name in {'accidentals', 'limiter'} else 6
    )

    def command(member: enum.Enum) -> None:
        _set_model_value(data, name, member, parent)
        _rebuild_note_grid_if_mapping_changed(parent, data)

    for i, member in enumerate(members):
        radio = QRadioButton(member.name, frame)
        radio.setMinimumWidth(radio.sizeHint().width())
        radio.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
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
        _checkpoint_undo(parent)
    object.__setattr__(data, name, getattr(validated, name))
    _clear_cached_values(data)
    if isinstance(data, Device):
        data.notify_change()


def _checkpoint_undo(parent: Any) -> None:
    root = _control_panel(parent).data
    if type(root).__name__ == 'Tuney':
        cast(Any, root).state.app.history.checkpoint_undo()


def _clear_cached_values(data: BaseModel) -> None:
    if type(data).__name__ == 'Tuney':
        cast(Any, data).state._clear_cached_values()
        return
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
    name: str, annotation: Any, display: Display | None = None
) -> int | None:
    display = display or Display()
    if display.width:
        return display.width * constants.ENTRY_CHAR_WIDTH

    types = set(_annotation_types(annotation))
    if str in types:
        return None
    if int in types and float not in types and bool not in types:
        return 4 * constants.ENTRY_CHAR_WIDTH
    if float in types:
        return (4 if display.step == 0.01 else 6) * constants.ENTRY_CHAR_WIDTH
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


def _parent_layout(parent: QWidget) -> QVBoxLayout | QHBoxLayout:
    layout = parent.layout()
    if layout is None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
    return cast(QVBoxLayout | QHBoxLayout, layout)


def _clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(cast(QVBoxLayout | QHBoxLayout, child_layout))


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
