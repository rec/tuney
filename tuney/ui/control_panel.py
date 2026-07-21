from __future__ import annotations

import enum
import inspect
import json
import math
from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING, Any, TypeAlias
from weakref import WeakKeyDictionary

from pydantic import BaseModel, TypeAdapter, ValidationError
from PySide6.QtCore import QLocale, QSignalBlocker, Qt, QTimer
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDial,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from tyro._fields import field_list_from_type_or_callable

from ..app.app import apply_preset
from ..app.platform_info import instrument
from ..audio.device import Device
from ..audio.midi import MIDIIn, MidiOut
from ..audio.polyphony import Polyphony
from ..config.display import General
from ..mapper.language import (
    alphabet_for_language_name,
    language_menu_names,
    language_name_from_menu_name,
)
from ..mapper.mapper import Mapper
from ..presets import merged_data, read_section_preset, section_preset_names
from ..scale.ratios import Ratios
from ..scale.scale import Scale
from ..scale.table import Table
from ..scale.tuning import Tuning, Type
from .control_panel_layout import _CurrentPageStackedWidget, _FlowLayout
from .control_panel_metadata import (
    _annotation_types,
    _control_metadata,
    _enum_class,
    _expects_json,
    _has_metadata,
    _numeric_metadata,
    _options_metadata,
)
from .control_panel_scala import (
    ScalaBrowserEdit,
    loaded_scala_description,
    loaded_scala_name,
)
from .control_panel_sizing import (
    ENTRY_CHAR_WIDTH,
    SPIN_BUTTON_WIDTH,
    _configure_editor,
    _configure_flexible_editor,
    _configure_label,
    _display_label,
    _entry_width,
)
from .control_panel_spin import _NumericDoubleSpinBox, _NumericSpinBox
from .control_panel_visibility import (
    _active_tuning_type,
    _has_visible_fields,
    _is_beginner_field,
    _is_wide_field,
    _midi_child_title,
    _model_tree,
    _visible_child_names,
    _visible_control_names,
)
from .tooltip import Tooltip

if TYPE_CHECKING:
    from ..app.app import App

Scalar: TypeAlias = bool | float | int | str | None

INLINE_CHILDREN = (Polyphony,)
SECTION_PRESET_PLACEHOLDER = 'Preset...'

CONTROL_BINDINGS: WeakKeyDictionary[QWidget, tuple[BaseModel, str, object | None]] = (
    WeakKeyDictionary()
)
INVALID_SCALE_WIDGET_TEXT_COLORS: WeakKeyDictionary[QLineEdit, str] = (
    WeakKeyDictionary()
)
NUMERIC_LOCALE = QLocale.c()
SPIN_MINIMUM = -9999
SPIN_MAXIMUM = 9999
SECTION_STYLE = """
QFrame#control_section {
    background: #f7f7f7;
    border: 1px solid #c8c8c8;
    border-radius: 4px;
}
QToolButton#control_section_disclosure {
    border: none;
    color: #303030;
    font-weight: 600;
    padding: 2px;
    text-align: left;
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
        value = getattr(self.data, self.name)
        choices = self.values()
        self.menu.clear()
        self.menu.addItems(['', *choices])
        self.menu.setCurrentText(_option_text(self.data, self.name, value, choices))


class ControlPanel(QScrollArea):
    def __init__(
        self,
        parent: QWidget,
        data: BaseModel,
        height: int = 200,
        app: App | None = None,
        build: bool = True,
        eager_modes: bool = True,
    ) -> None:
        instrument('control panel init', model=type(data).__name__)
        super().__init__(parent)
        self.data = data
        self.app = app
        self.option_controls: list[_OptionControl] = []
        self.show_advanced = True
        self.eager_modes = eager_modes
        self.pages: dict[bool, QWidget] = {}
        self.setWidgetResizable(True)
        self.setMinimumHeight(min(height, 80))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content: QStackedWidget = QStackedWidget()
        self.content.setObjectName('control_panel_content')
        self.setWidget(self.content)
        if build:
            self.rebuild()
        else:
            self._add_placeholder()

    def rebuild(self) -> None:
        instrument('control panel rebuild start', model=type(self.data).__name__)
        while self.content.count():
            page = self.content.widget(0)
            assert page is not None
            self.content.removeWidget(page)
            page.deleteLater()
        self.pages.clear()
        self.option_controls.clear()
        self.pages[self.show_advanced] = self._build_page(self.show_advanced)
        if self.eager_modes:
            other_mode = not self.show_advanced
            self.pages[other_mode] = self._build_page(other_mode)
        self.content.setCurrentWidget(self.pages[self.show_advanced])
        instrument('control panel rebuild end', model=type(self.data).__name__)

    def show_mode(self, advanced: bool) -> None:
        instrument('control panel show mode', advanced=advanced)
        if advanced == self.show_advanced and advanced in self.pages:
            return
        self.show_advanced = advanced
        if advanced not in self.pages:
            self.pages[advanced] = self._build_page(advanced)
        self.content.setCurrentWidget(self.pages[advanced])

    def _build_page(self, advanced: bool) -> QWidget:
        instrument('control panel build page start', advanced=advanced)
        page = QWidget(self.content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        self.content.addWidget(page)
        if type(self.data).__name__ == 'Tuney':
            _add_general_controls(
                page,
                self.data,
                self.option_controls,
                advanced,
            )
        _add_model_controls(page, self.data, self.option_controls, advanced=advanced)
        instrument('control panel build page end', advanced=advanced)
        return page

    def _add_placeholder(self) -> None:
        page = QWidget(self.content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(QLabel('Loading controls...', page))
        self.content.addWidget(page)


def _set_control_panel_mode(control_panel: ControlPanel, advanced: bool) -> None:
    control_panel.show_mode(advanced)


def _add_model_controls(
    parent: QWidget,
    data: BaseModel,
    option_controls: list[_OptionControl],
    title: str | None = None,
    advanced: bool = True,
) -> None:
    if title:
        parent = _add_collapsible_section(parent, title, data)

    if isinstance(data, Tuning):
        _add_tuning_controls(parent, data, option_controls, advanced)
        return

    controls = _visible_control_names(data, advanced)
    children = [
        name
        for name in _visible_child_names(data, advanced)
        if not isinstance(getattr(data, name), INLINE_CHILDREN)
    ]

    if controls:
        _add_control_grid(parent, data, controls, option_controls, advanced)
        if isinstance(data, Scale):
            _add_scala_browser_control(parent, data)

    for name in children:
        child = getattr(data, name)
        assert isinstance(child, BaseModel)
        if not _has_visible_fields(child, advanced):
            continue
        if not _visible_control_names(child, advanced):
            _add_model_controls(parent, child, option_controls, advanced=advanced)
            continue
        _add_model_controls(
            parent,
            child,
            option_controls,
            _midi_child_title(data, name),
            advanced,
        )


def _add_tuning_controls(
    parent: QWidget,
    data: Tuning,
    option_controls: list[_OptionControl],
    advanced: bool,
) -> None:
    controls = [
        name
        for name in ['type', 'detune', 'root_frequency', 'root_note']
        if advanced or _is_beginner_field(data, name)
    ]
    _add_control_grid(parent, data, controls, option_controls, advanced)

    stack = _CurrentPageStackedWidget(parent)
    stack.setObjectName('tuning_form_stack')
    for tuning_type in Type:
        page = QWidget(stack)
        page.setObjectName(f'tuning_form_{tuning_type.value}')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        match tuning_type:
            case Type.computed:
                if data.computed is not None:
                    _add_model_controls(
                        page, data.computed, option_controls, advanced=advanced
                    )
            case Type.table:
                _add_control_group_grid(page, [(data, 'table')], option_controls)
            case Type.ratios:
                _add_control_group_grid(page, [(data, 'ratios')], option_controls)
        stack.addWidget(page)
    _parent_layout(parent).addWidget(stack)
    _set_tuning_form(stack, data)


def _add_general_controls(
    parent: QWidget,
    data: BaseModel,
    option_controls: list[_OptionControl],
    advanced: bool = True,
) -> None:
    if not (controls := _general_controls(data, advanced)):
        return
    body = _add_collapsible_section(parent, 'general')
    _add_control_group_grid(body, controls, option_controls)


def _section(parent: QWidget) -> QFrame:
    section = QFrame(parent)
    section.setObjectName('control_section')
    section.setFrameShape(QFrame.Shape.StyledPanel)
    section.setStyleSheet(SECTION_STYLE)
    return section


def _add_collapsible_section(
    parent: QWidget, title: str, data: BaseModel | None = None
) -> QWidget:
    section = _section(parent)
    _parent_layout(parent).addWidget(section)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(6, 4, 6, 6)
    layout.setSpacing(3)

    body = QWidget(section)
    body.setObjectName('control_section_body')
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(3)

    button = QToolButton(section)
    button.setObjectName('control_section_disclosure')
    button.setText(_display_label(title))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setArrowType(Qt.ArrowType.DownArrow)
    button.setCheckable(True)
    button.setChecked(True)
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    button.toggled.connect(lambda checked: _set_section_expanded(button, body, checked))

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(6)
    header.addWidget(button)
    _add_section_preset_control(section, header, data)

    layout.addLayout(header)
    layout.addWidget(body)
    return body


def _set_section_expanded(button: QToolButton, body: QWidget, expanded: bool) -> None:
    body.setVisible(expanded)
    button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)


def _add_section_preset_control(
    parent: QWidget,
    layout: QBoxLayout,
    data: BaseModel | None,
) -> None:
    section = _section_preset_section(data)
    if section is None or not (names := section_preset_names(section)):
        return
    assert data is not None

    menu = QComboBox(parent)
    menu.setObjectName('section_preset')
    menu.addItems([SECTION_PRESET_PLACEHOLDER, *names])
    menu.setCurrentIndex(0)
    menu.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    layout.addWidget(menu)

    def command(name: str) -> None:
        if name == SECTION_PRESET_PLACEHOLDER:
            return
        _apply_section_preset(parent, data, section, name)
        blocker = QSignalBlocker(menu)
        menu.setCurrentIndex(0)
        del blocker

    menu.currentTextChanged.connect(command)


def _section_preset_section(data: BaseModel | None) -> str | None:
    if isinstance(data, Scale):
        return 'scale'
    if isinstance(data, Tuning):
        return 'tuning'
    return None


def _apply_section_preset(
    parent: QWidget, data: BaseModel, section: str, name: str
) -> None:
    values = merged_data(data.model_dump(), read_section_preset(section, name))
    validated = type(data).model_validate(values)
    if data.model_dump() != validated.model_dump():
        _checkpoint_undo(parent)
    for field in type(data).model_fields:
        setattr(data, field, getattr(validated, field))
    _clear_cached_values(data)
    _after(parent, 0, _rebuild_parent_control_panel, parent)
    _rebuild_note_grid_if_mapping_changed(parent, data)


def _general_controls(data: Any, advanced: bool = True) -> list[tuple[BaseModel, str]]:
    return [
        (model, name)
        for model in _model_tree(data)
        for name in type(model).model_fields
        if _has_metadata(type(model), name, General)
        and (advanced or _is_beginner_field(model, name))
    ]


def _add_control_group_grid(
    parent: QWidget,
    controls: list[tuple[BaseModel, str]],
    option_controls: list[_OptionControl],
) -> None:
    _add_control_flow(parent, controls, option_controls)


def _add_control_grid(
    parent: QWidget,
    data: BaseModel,
    fields: list[str],
    option_controls: list[_OptionControl],
    advanced: bool,
) -> None:
    _add_control_flow(parent, _control_refs(data, fields, advanced), option_controls)


def _add_control_flow(
    parent: QWidget,
    controls: list[tuple[BaseModel, str]],
    option_controls: list[_OptionControl],
) -> None:
    frame = QWidget(parent)
    layout = _FlowLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    for control_data, name in controls:
        _add_control_cell(frame, control_data, name, option_controls)
    _parent_layout(parent).addWidget(frame)


def _control_refs(
    data: BaseModel, fields: list[str], advanced: bool
) -> list[tuple[BaseModel, str]]:
    controls = [(data, name) for name in fields]
    for name in _visible_child_names(data, advanced):
        child = getattr(data, name)
        if isinstance(child, INLINE_CHILDREN):
            controls.extend(
                (child, child_name)
                for child_name in _visible_control_names(child, advanced)
            )
    return controls


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
    else:
        cell.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    parent_layout = parent.layout()
    assert parent_layout is not None
    parent_layout.addWidget(cell)

    _add_control(cell, data, name, option_controls)
    _add_field_tooltips(cell, type(data), name)
    cell.setProperty('control_field_name', name)
    _bind_control(cell, data, name)
    if isinstance(data, MIDIIn | MidiOut) and not data.enable and name != 'enable':
        _set_widget_state(cell, False)


def _add_field_tooltips(parent: QWidget, model: type[BaseModel], name: str) -> None:
    control_panel = _control_panel(parent)
    for widget in _field_widgets(parent):
        if isinstance(widget, QWidget) and not widget.property('skip_field_tooltip'):
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


def _add_control(
    parent: QWidget,
    data: BaseModel,
    name: str,
    option_controls: list[_OptionControl],
) -> None:
    value = getattr(data, name)
    annotation = type(data).model_fields[name].annotation
    enum_cls = _enum_class(annotation, value)

    if options := _options_metadata(type(data), name):
        _add_option_control(parent, data, name, value, options.options, option_controls)
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
    choices = values()
    menu.addItems(['', *choices])
    menu.setCurrentText(_option_text(data, name, value, choices))
    _bind_control(menu, data, name)

    def command(raw: str) -> None:
        if type(data).__name__ == 'Tuney' and name == 'preset' and raw:
            _checkpoint_undo(parent)
            state = _control_panel(parent).app
            assert state is not None
            apply_preset(state, raw)
            _after(parent, 0, _rebuild_parent_control_panel, parent)
            _after(parent, 0, _rebuild_note_grid, parent)
        else:
            _set_model_value(data, name, raw or None, parent)
            _rebuild_note_grid_if_mapping_changed(parent, data)

    menu.currentTextChanged.connect(command)
    layout.addWidget(menu)
    _parent_layout(parent).addWidget(frame)
    option_controls.append(_OptionControl(menu, data, name, values))


def _add_scala_browser_control(parent: QWidget, data: Scale) -> None:
    frame, layout, _ = _add_labeled_control_frame(parent, 'scala')
    app = _control_panel(parent).app
    entry = ScalaBrowserEdit(frame, app, _load_scala_browser_tuning, _set_app_tuning)
    _configure_editor(entry, 12 * ENTRY_CHAR_WIDTH)
    entry.setObjectName('scala_browser')
    layout.addWidget(entry)
    if app is not None:
        checkbox = QCheckBox('audition', frame)
        checkbox.setChecked(app.audition_scala)

        def update(checked: bool) -> None:
            app.audition_scala = checked
            entry.set_audition(checked)

        checkbox.toggled.connect(update)
        layout.addWidget(checkbox)
    name = QLineEdit(loaded_scala_name(app), frame)
    name.setReadOnly(True)
    _configure_editor(name, 7 * ENTRY_CHAR_WIDTH)
    name.setObjectName('tuning_name')
    layout.addWidget(name)
    description = QLineEdit(loaded_scala_description(app), frame)
    description.setReadOnly(True)
    _configure_flexible_editor(description, 120 * ENTRY_CHAR_WIDTH)
    description.setObjectName('tuning_description')
    layout.addWidget(description)
    _parent_layout(parent).addWidget(frame)


def _load_scala_browser_tuning(entry: ScalaBrowserEdit) -> None:
    if (ratios := entry.selected_ratios()) is None:
        return
    parent = entry.parentWidget()
    assert parent is not None
    if (
        QMessageBox.question(
            parent,
            'Load Scala tuning',
            f'Load {ratios.name}?',
        )
        != QMessageBox.StandardButton.Yes
    ):
        return
    control_panel = _control_panel(parent)
    app = control_panel.app
    assert app is not None
    entry.restore_audition()
    app.main_window.history.checkpoint_undo()
    _set_app_tuning(app, ratios)
    _set_loaded_scala_fields(control_panel, ratios)
    app.main_window.ui.rebuild_control_panel()


def _set_loaded_scala_fields(control_panel: ControlPanel, ratios: Ratios) -> None:
    if name := control_panel.findChild(QLineEdit, 'tuning_name'):
        name.setText(ratios.name.removesuffix('.scl'))
    if description := control_panel.findChild(QLineEdit, 'tuning_description'):
        description.setText(ratios.desc)


def _set_app_tuning(app: App, tuning: Tuning | Ratios) -> None:
    data = (
        tuning.model_dump()
        if isinstance(tuning, Tuning)
        else app.tuning.model_dump() | {'type': Type.ratios, 'ratios': tuning}
    )
    validated = type(app.tuning).model_validate(data)
    for field in type(app.tuning).model_fields:
        setattr(app.tuning, field, getattr(validated, field))
    _clear_cached_values(app.tuning)
    if (player := app.__dict__.pop('player', None)) is not None:
        player.close()


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
    state = _control_panel(parent).app
    assert state is not None
    state.main_window.ui.rebuild_note_grid()


def _add_bool_control(parent: QWidget, data: BaseModel, name: str, value: bool) -> None:
    check = QCheckBox(_display_label(name), parent)
    check.setMinimumWidth(check.sizeHint().width())
    check.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    check.setChecked(value)
    _bind_control(check, data, name)

    def command(checked: bool) -> None:
        _set_model_value(data, name, checked, parent)
        _rebuild_note_grid_if_mapping_changed(parent, data)
        if isinstance(data, MIDIIn | MidiOut) and name == 'enable':
            _set_midi_controls_state(parent, checked)
            if isinstance(data, MIDIIn) and (state := _control_panel(parent).app):
                if checked:
                    state.midi_input_listener.start()
                else:
                    state.midi_input_listener.close()

    check.toggled.connect(command)
    _parent_layout(parent).addWidget(check)


def _set_midi_controls_state(parent: QWidget, enabled: bool) -> None:
    data = CONTROL_BINDINGS[parent][0]
    for cell in _control_panel(parent).findChildren(QWidget):
        field = cell.property('control_field_name')
        binding = CONTROL_BINDINGS.get(cell)
        if binding and binding[0] is data and field and field != 'enable':
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
    text = _entry_text(data, name, value, annotation)

    frame, layout, _ = _add_labeled_control_frame(parent, name)
    entry = QLineEdit(text, frame)
    _bind_control(entry, data, name)
    width = _entry_width(
        name,
        annotation,
        _control_metadata(type(data), name),
        _numeric_metadata(type(data), name),
    )
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
    if isinstance(data, Mapper) and name == 'alphabet':
        _add_alphabet_language_menu(frame, layout, data, entry, update)
    _parent_layout(parent).addWidget(frame)


def _add_alphabet_language_menu(
    frame: QWidget,
    layout: QBoxLayout,
    data: Mapper,
    entry: QLineEdit,
    update: Callable[[], None],
) -> None:
    menu = QComboBox(frame)
    menu.setObjectName('alphabet_language')
    menu.addItems(['Language...', '(clear)', *language_menu_names()])
    menu.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def command(name: str) -> None:
        if name == 'Language...':
            return
        entry.setText(
            ''
            if name == '(clear)'
            else alphabet_for_language_name(
                language_name_from_menu_name(name), data.case_sensitive
            )
        )
        update()
        menu.setCurrentIndex(0)

    menu.currentTextChanged.connect(command)
    layout.addWidget(menu)


def _add_spin_control(
    parent: QWidget, data: BaseModel, name: str, value: object
) -> None:
    annotation = type(data).model_fields[name].annotation
    numeric = _numeric_metadata(type(data), name)
    frame, layout, _ = _add_labeled_control_frame(parent, name)

    if _is_int_annotation(annotation):
        assert isinstance(value, int)
        spin = _NumericSpinBox(frame)
        spin.setLocale(NUMERIC_LOCALE)
        minimum = math.ceil(numeric.min) if numeric.min is not None else SPIN_MINIMUM
        maximum = math.floor(numeric.max) if numeric.max is not None else SPIN_MAXIMUM
        spin.setRange(minimum, maximum)
        if numeric.inc is not None:
            spin.setSingleStep(max(1, round(numeric.inc)))
        spin.setValue(value)
        _bind_control(spin, data, name)

        def update() -> None:
            _set_model_value(data, name, spin.value(), parent)
            _rebuild_note_grid_if_mapping_changed(parent, data)

        spin.editingFinished.connect(update)
        layout.addWidget(spin)
    else:
        assert isinstance(value, float | int)
        spin = _NumericDoubleSpinBox(frame, numeric)
        spin.setLocale(NUMERIC_LOCALE)
        spin.setDecimals(numeric.displayed_decimals)
        spin.setRange(
            numeric.min if numeric.min is not None else float(SPIN_MINIMUM),
            numeric.max if numeric.max is not None else float(SPIN_MAXIMUM),
        )
        spin.setSingleStep(numeric.increment)
        spin.setValue(float(value))
        _bind_control(spin, data, name)

        def update() -> None:
            _set_model_value(data, name, spin.value(), parent)
            _rebuild_note_grid_if_mapping_changed(parent, data)

        spin.editingFinished.connect(update)
        layout.addWidget(spin)

        if numeric.dial:
            dial = QDial(frame)
            dial.setFixedSize(30, 30)
            dial.setWrapping(False)
            dial.setRange(0, 100)
            dial.setValue(numeric.spin_to_dial(spin.value()))
            _bind_control(dial, data, name)
            dial.valueChanged.connect(
                lambda value: spin.setValue(numeric.dial_to_spin(value))
            )
            dial.sliderReleased.connect(update)
            layout.addWidget(dial)

    width = _entry_width(name, annotation, _control_metadata(type(data), name), numeric)
    _configure_editor(spin, width + SPIN_BUTTON_WIDTH if width else None)
    _parent_layout(parent).addWidget(frame)


def _can_use_spin_control(annotation: Any, value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    return (
        isinstance(value, int | float)
        and SPIN_MINIMUM <= value <= SPIN_MAXIMUM
        and (_is_int_annotation(annotation) or float in _annotation_types(annotation))
    )


def _is_int_annotation(annotation: Any) -> bool:
    types = _annotation_types(annotation)
    return int in types and float not in types and bool not in types


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
        if isinstance(data, Tuning) and name == 'type':
            _set_tuning_type_form(parent, data)
        _rebuild_note_grid_if_mapping_changed(parent, data)

    for i, member in enumerate(members):
        radio = QRadioButton(member.name, frame)
        radio.setMinimumWidth(radio.sizeHint().width())
        radio.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        radio.setChecked(i == index)
        radio.setProperty('skip_field_tooltip', True)
        Tooltip(
            radio,
            _enum_hover_text(member),
            lambda: float(getattr(_control_panel(parent).data, 'hover_time', 1.0)),
        )
        _bind_control(radio, data, name, member)
        radio.toggled.connect(
            lambda checked, member=member: checked and command(member)
        )
        layout.addWidget(radio)
    _parent_layout(parent).addWidget(frame)


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


def _set_tuning_type_form(parent: QWidget, data: Tuning) -> None:
    for stack in _control_panel(parent).findChildren(
        QStackedWidget, 'tuning_form_stack'
    ):
        _set_tuning_form(stack, data)


def _set_tuning_form(stack: QStackedWidget, data: Tuning) -> None:
    stack.setCurrentIndex(list(Type).index(_active_tuning_type(data)))
    stack.updateGeometry()


def _set_model_value(
    data: BaseModel, name: str, value: object, parent: Any | None = None
) -> None:
    instrument('control value set start', model=type(data).__name__, field=name)
    values = data.model_dump()
    values[name] = value
    validated = type(data).model_validate(values)
    validated_value = getattr(validated, name)
    if isinstance(validated_value, Table) and not validated_value.values:
        raise ValueError('No frequency table configured')
    if isinstance(validated_value, Ratios) and not validated_value.ratios:
        raise ValueError('No tuning ratios configured')
    if parent is not None and getattr(data, name) != getattr(validated, name):
        _checkpoint_undo(parent)
    setattr(data, name, validated_value)
    _clear_cached_values(data)
    if isinstance(data, Device):
        data.notify_change()
    if parent is not None:
        _sync_model_controls(parent, data, name)
    instrument('control value set end', model=type(data).__name__, field=name)


def _checkpoint_undo(parent: Any) -> None:
    control_panel = _control_panel(parent)
    if type(control_panel.data).__name__ == 'Tuney':
        assert control_panel.app is not None
        control_panel.app.main_window.history.checkpoint_undo()


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
    INVALID_SCALE_WIDGET_TEXT_COLORS.setdefault(widget, text_color)
    widget.setStyleSheet('color: red;')


def _clear_invalid_scale_widgets() -> None:
    for widget in tuple(INVALID_SCALE_WIDGET_TEXT_COLORS):
        widget.setStyleSheet('')
        INVALID_SCALE_WIDGET_TEXT_COLORS.pop(widget, None)


def _parse_entry_value(
    raw: str, annotation: Any, old_value: object, name: str = ''
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


def _entry_text(data: BaseModel, name: str, value: object, annotation: Any) -> str:
    if isinstance(data, Scale) and name == 'intervals' and isinstance(value, list):
        return ''.join(str(i) for i in value)
    if isinstance(data, Tuning) and name in {'table', 'ratios'}:
        return _tuning_expression_text(value)
    if value is None:
        return ''
    if isinstance(value, list | dict):
        return json.dumps(TypeAdapter(annotation).dump_python(value, mode='json'))
    return str(value)


def _bind_control(
    widget: QWidget,
    data: BaseModel,
    name: str,
    choice: object | None = None,
) -> None:
    CONTROL_BINDINGS[widget] = data, name, choice


def _sync_model_controls(parent: QWidget, data: BaseModel, name: str) -> None:
    value = getattr(data, name)
    annotation = type(data).model_fields[name].annotation
    numeric = _numeric_metadata(type(data), name)
    for widget in _control_panel(parent).findChildren(QWidget):
        binding = CONTROL_BINDINGS.get(widget)
        if not binding or binding[0] is not data or binding[1] != name:
            continue
        blocker = QSignalBlocker(widget)
        if isinstance(widget, QRadioButton):
            widget.setChecked(value == binding[2])
        elif isinstance(widget, QComboBox):
            choices = [widget.itemText(i) for i in range(widget.count())]
            widget.setCurrentText(_option_text(data, name, value, choices))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QDial) and isinstance(value, int | float):
            widget.setValue(numeric.spin_to_dial(float(value)))
        elif isinstance(widget, QSpinBox) and isinstance(value, int):
            widget.setValue(value)
        elif isinstance(widget, QDoubleSpinBox) and isinstance(value, int | float):
            widget.setValue(float(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(_entry_text(data, name, value, annotation))
        del blocker


def _option_text(data: BaseModel, name: str, value: object, choices: list[str]) -> str:
    if value is None:
        return ''
    if isinstance(data, Device) and name == 'device' and isinstance(value, int):
        prefix = f'[{value}] '
        if choice := next((i for i in choices if i.startswith(prefix)), ''):
            return choice
    return str(value)


def _parent_layout(parent: QWidget) -> QBoxLayout:
    if (layout := parent.layout()) is None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
    assert isinstance(layout, QBoxLayout)
    return layout


def _after(
    parent: Any, delay: int, callback: Callable[..., object], *args: object
) -> None:
    if hasattr(parent, 'after'):
        parent.after(delay, callback, *args)
    else:
        QTimer.singleShot(delay, lambda: callback(*args))
