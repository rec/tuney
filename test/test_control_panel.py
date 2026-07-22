import subprocess
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import get_origin

import pytest
import tomlkit
from pydantic import BaseModel

from tuney import midi as midi_module
from tuney.app.app import App
from tuney.app.global_config import GlobalConfig
from tuney.audio import device as device_module
from tuney.audio.device import Device
from tuney.audio.oscillator import Oscillator
from tuney.audio.polyphony import Polyphony
from tuney.audio.sound import Sound
from tuney.config.display import Numeric, Options
from tuney.config.tuney import Tuney
from tuney.mapper.mapper import Mapper
from tuney.midi import MIDIIn, MidiOut
from tuney.midi import ports as midi_ports
from tuney.scale.ratios import Ratios
from tuney.scale.scala_browser import build_trie
from tuney.scale.scale import Scale
from tuney.scale.table import Table
from tuney.scale.tuning import Computed, Tuning, Type
from tuney.time.text_timings import TextTimings
from tuney.ui import (
    control_panel,
    control_panel_scala,
    control_panel_sizing,
    control_panel_spin,
    control_panel_visibility,
)


@pytest.fixture(autouse=True)
def stub_external_option_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    midi_module.input_names.cache_clear()
    midi_module.output_names.cache_clear()
    device_module.device_names.cache_clear()
    monkeypatch.setattr(
        midi_ports.subprocess,
        'run',
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, '[]', ''),
    )
    monkeypatch.setattr(device_module.sounddevice, 'query_devices', lambda: [])


def _check_regression(file_regression, actual: Mapping[str, object]) -> None:
    file_regression.check(tomlkit.dumps(_regression_data(actual)), extension='.toml')


def _regression_data(data: Mapping[str, object]) -> dict[str, object]:
    return {name: _regression_value(value) for name, value in data.items()}


def _regression_value(value: object) -> object:
    if value is None:
        return 'None'
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool | float | int | str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _regression_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_regression_value(item) for item in value]
    return str(value)


def _entry_width(cls: type[BaseModel], name: str) -> int | None:
    return control_panel._entry_width(
        name,
        cls.model_fields[name].annotation,
        control_panel._control_metadata(cls, name),
        control_panel._numeric_metadata(cls, name),
    )


def _is_scalar_numeric_field(cls: type[BaseModel], name: str) -> bool:
    annotation = cls.model_fields[name].annotation
    if any(isinstance(i, Options) for i in cls.model_fields[name].metadata):
        return False
    if get_origin(annotation) in {list, dict}:
        return False
    types = set(control_panel._annotation_types(annotation))
    if list in types or dict in types or bool in types:
        return False
    return bool(types & {int, float})


def _model_classes(data: BaseModel) -> list[type[BaseModel]]:
    classes = [type(data)]
    for name in type(data).model_fields:
        value = getattr(data, name)
        if isinstance(value, BaseModel):
            classes.extend(_model_classes(value))
    return classes


def _qt_app() -> object:
    from PySide6.QtWidgets import QApplication

    if (app := QApplication.instance()) is None:
        app = QApplication([])
    return app


def test_set_model_value_validates_and_clears_cached_values(
    file_regression,
) -> None:
    mapper = Mapper(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
    before = mapper.char_to_number['b']

    control_panel._set_model_value(mapper, 'length', '1')

    _check_regression(
        file_regression,
        {
            'before': before,
            'length': mapper.length,
            'after': mapper.char_to_number['b'],
        },
    )


def test_mapper_length_spinbox_cannot_go_below_zero() -> None:
    from PySide6.QtWidgets import QSpinBox, QWidget

    _qt_app()
    mapper = Mapper()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, mapper)
    editors = [
        widget
        for widget in panel.findChildren(QSpinBox)
        if control_panel.CONTROL_BINDINGS.get(widget, (None,))[0] is mapper
        and control_panel.CONTROL_BINDINGS[widget][1] == 'length'
    ]

    assert len(editors) == 1
    assert {editor.minimum() for editor in editors} == {0}


def test_set_model_value_converts_dtype_string(
    file_regression,
) -> None:
    device = Device()

    control_panel._set_model_value(device, 'dtype', 'int16')

    _check_regression(file_regression, {'dtype': device.dtype})


def test_set_model_value_notifies_device_change(
    file_regression,
) -> None:
    device = Device()
    changes: list[bool] = []
    device.set_change_callback(lambda: changes.append(True))

    control_panel._set_model_value(device, 'device', 'speaker')

    _check_regression(file_regression, {'changes': changes})


def test_scale_and_mapper_changes_schedule_note_grid_rebuild(
    file_regression,
) -> None:
    scheduled: list[tuple[int, object, tuple[object, ...]]] = []

    class Parent:
        def after(self, delay: int, callback: object, *args: object) -> None:
            scheduled.append((delay, callback, args))

    parent = Parent()

    control_panel._rebuild_note_grid_if_mapping_changed(parent, Scale())
    control_panel._rebuild_note_grid_if_mapping_changed(parent, Mapper())

    _check_regression(
        file_regression,
        {
            'count': len(scheduled),
            'delays': [item[0] for item in scheduled],
        },
    )


def test_scale_note_errors_report_bad_notes_without_failing(
    file_regression,
) -> None:
    _check_regression(
        file_regression,
        {
            'bad_notes': control_panel._scale_note_errors(Scale(notes='C frog D')),
            'good_notes': control_panel._scale_note_errors(Scale(notes='C D')),
        },
    )


def test_scale_has_note_buttons_rejects_non_positive_note_count(
    file_regression,
) -> None:
    _check_regression(
        file_regression,
        {
            'default': control_panel._scale_has_note_buttons(Scale()),
            'zero_interval': control_panel._scale_has_note_buttons(
                Scale(intervals=[0])
            ),
        },
    )


def test_parse_entry_value_parses_optional_lists_as_json(
    file_regression,
) -> None:
    annotation = TextTimings.model_fields['timings'].annotation

    _check_regression(
        file_regression,
        {'value': control_panel._parse_entry_value('[1, 2]', annotation, None)},
    )


def test_parse_entry_value_keeps_intervals_as_text(
    file_regression,
) -> None:
    annotation = Scale.model_fields['intervals'].annotation

    _check_regression(
        file_regression,
        {
            'value': control_panel._parse_entry_value(
                '221 2221', annotation, [2], 'intervals'
            )
        },
    )


def test_parse_entry_value_keeps_text_as_text(
    file_regression,
) -> None:
    annotation = Tuney.model_fields['text'].annotation

    _check_regression(
        file_regression,
        {'value': control_panel._parse_entry_value('hello', annotation, None)},
    )


def test_entry_width_uses_compact_numeric_widths(
    file_regression,
) -> None:
    _check_regression(
        file_regression,
        {
            'max_gap': _entry_width(Tuney, 'max_gap'),
            'mapper_alphabet': _entry_width(Mapper, 'alphabet'),
            'mapper_length': _entry_width(Mapper, 'length'),
            'mapper_offset': _entry_width(Mapper, 'offset'),
            'mapper_range_limit': _entry_width(Mapper, 'range_limit'),
            'scale_root': _entry_width(Scale, 'root'),
            'scale_begin': _entry_width(Scale, 'begin'),
            'scale_end': _entry_width(Scale, 'end'),
            'scale_notes': _entry_width(Scale, 'notes'),
            'scale_intervals': _entry_width(Scale, 'intervals'),
            'scale_offset': _entry_width(Scale, 'offset'),
            'detune': _entry_width(Tuning, 'detune'),
            'limit': _entry_width(Computed, 'limit'),
            'notes_per_octave': _entry_width(Computed, 'notes_per_octave'),
            'octave_ratio': _entry_width(Computed, 'octave_ratio'),
            'headroom': _entry_width(Polyphony, 'headroom'),
            'max_voices': _entry_width(Polyphony, 'max_voices'),
            'duty_cycle': _entry_width(Oscillator, 'duty_cycle'),
            'key_scale_note': _entry_width(Oscillator, 'key_scale_note'),
            'key_scale': _entry_width(Oscillator, 'key_scale'),
            'midi_channel': _entry_width(MidiOut, 'channel'),
            'midi_velocity': _entry_width(MidiOut, 'velocity'),
            'midi_note_offset': _entry_width(MidiOut, 'note_offset'),
            'overlap': _entry_width(TextTimings, 'overlap'),
            'gain': _entry_width(Sound, 'gain'),
            'scale': _entry_width(TextTimings, 'scale'),
            'frequency': _entry_width(Tuning, 'root_frequency'),
            'note': _entry_width(Tuning, 'root_note'),
            'device': _entry_width(Device, 'device'),
            'sample_rate': _entry_width(Device, 'sample_rate'),
            'dtype': _entry_width(Device, 'dtype'),
            'space': _entry_width(TextTimings, 'space'),
            'root': _entry_width(Scale, 'root'),
            'midi_name': _entry_width(MidiOut, 'name'),
        },
    )


def test_numeric_width_sets_actual_editor_width() -> None:
    from PySide6.QtWidgets import QLineEdit, QSpinBox, QWidget

    _qt_app()
    mapper = Mapper()
    scale = Scale()
    mapper_parent = QWidget()
    scale_parent = QWidget()
    mapper_panel = control_panel.ControlPanel(mapper_parent, mapper)
    scale_panel = control_panel.ControlPanel(scale_parent, scale)

    mapper_editors = {
        control_panel.CONTROL_BINDINGS[w][1]: w
        for w in mapper_panel.findChildren(QSpinBox)
        if control_panel.CONTROL_BINDINGS.get(w, (None,))[0] is mapper
    }
    scale_editors = {
        control_panel.CONTROL_BINDINGS[w][1]: w
        for w in scale_panel.findChildren(QLineEdit)
        if control_panel.CONTROL_BINDINGS.get(w, (None,))[0] is scale
    }

    assert mapper_editors['length'].minimumWidth() == (
        _entry_width(Mapper, 'length') + control_panel_sizing.SPIN_BUTTON_WIDTH
    )
    assert mapper_editors['offset'].minimumWidth() == (
        _entry_width(Mapper, 'offset') + control_panel_sizing.SPIN_BUTTON_WIDTH
    )
    assert scale_editors['root'].minimumWidth() == _entry_width(Scale, 'root')
    assert scale_editors['begin'].minimumWidth() == _entry_width(Scale, 'begin')
    assert scale_editors['end'].minimumWidth() == _entry_width(Scale, 'end')


def test_numeric_metadata_configures_steps_and_decimals() -> None:
    assert control_panel._numeric_metadata(Tuning, 'detune').decimals == 0
    assert control_panel._numeric_metadata(Tuning, 'detune').inc == 1
    assert control_panel._numeric_metadata(Computed, 'octave_ratio').inc == 0.001
    assert control_panel._numeric_metadata(Polyphony, 'headroom').decimals == 0
    assert control_panel._numeric_metadata(Polyphony, 'headroom').inc == 1
    assert control_panel._numeric_metadata(Oscillator, 'duty_cycle').inc == 0.01
    assert control_panel._numeric_metadata(TextTimings, 'overlap').decimals == 0
    assert control_panel._numeric_metadata(TextTimings, 'overlap').inc == 1
    assert control_panel._numeric_metadata(TextTimings, 'scale').decimals is None


def test_display_labels_use_sentence_case() -> None:
    assert control_panel._display_label('text_timings') == 'Text timings'
    assert control_panel._display_label('sample_rate') == 'Sample rate'


def test_indexed_output_device_option_displays_choice_text() -> None:
    assert (
        control_panel._option_text(
            Device(device=7),
            'device',
            7,
            ['[3] Speakers', '[7] Speakers'],
        )
        == '[7] Speakers'
    )


def test_general_midi_program_option_displays_choice_text() -> None:
    assert (
        control_panel._option_text(
            MidiOut(program=40),
            'program',
            40,
            ['1 Acoustic Grand Piano', '41 Violin'],
        )
        == '41 Violin'
    )


def test_general_midi_program_change_is_sent_to_open_port() -> None:
    messages = []

    class Port:
        def send(self, message: object) -> None:
            messages.append(message)

    midi = MidiOut(program=0)
    midi.__dict__['outport'] = Port()

    control_panel._set_model_value(midi, 'program', '41 Violin')

    assert midi.program == 40
    assert messages[0].type == 'program_change'
    assert messages[0].program == 40
    assert 'outport' not in midi.__dict__


def test_control_flow_layout_wraps_to_available_width() -> None:
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QLabel, QWidget

    _qt_app()
    parent = QWidget()
    layout = control_panel._FlowLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    labels = [QLabel(str(i), parent) for i in range(3)]
    for label in labels:
        label.setFixedSize(40, 10)
        layout.addWidget(label)

    layout.setGeometry(QRect(0, 0, 200, 100))

    assert [(i.geometry().x(), i.geometry().y()) for i in labels] == [
        (0, 0),
        (46, 0),
        (92, 0),
    ]

    layout.setGeometry(QRect(0, 0, 90, 100))

    assert [(i.geometry().x(), i.geometry().y()) for i in labels] == [
        (0, 0),
        (46, 0),
        (0, 16),
    ]


def test_tuning_stack_sizes_to_current_form() -> None:
    from PySide6.QtWidgets import QLabel, QWidget

    _qt_app()
    parent = QWidget()
    stack = control_panel._CurrentPageStackedWidget(parent)
    small = QLabel('small', stack)
    small.setFixedSize(40, 10)
    large = QLabel('large', stack)
    large.setFixedSize(40, 80)
    stack.addWidget(small)
    stack.addWidget(large)

    stack.setCurrentWidget(small)

    assert stack.sizeHint().height() == small.sizeHint().height()

    stack.setCurrentWidget(large)

    assert stack.sizeHint().height() == large.sizeHint().height()


def test_beginner_mode_filters_advanced_controls(
    file_regression,
) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            'mapper_controls': control_panel._visible_control_names(
                tuney.mapper, advanced=False
            ),
            'tuney_children': control_panel._visible_child_names(tuney, advanced=False),
            'tuney_controls': control_panel._visible_control_names(
                tuney, advanced=False
            ),
        },
    )


def test_control_panel_reuses_mode_pages(monkeypatch) -> None:
    from PySide6.QtWidgets import QWidget

    _qt_app()
    calls: list[bool] = []
    add_model_controls = control_panel._add_model_controls

    def wrapped_add_model_controls(
        parent: QWidget,
        data: BaseModel,
        option_controls: list[object],
        title: str | None = None,
        advanced: bool = True,
    ) -> None:
        calls.append(advanced)
        add_model_controls(parent, data, option_controls, title, advanced)

    monkeypatch.setattr(
        control_panel, '_add_model_controls', wrapped_add_model_controls
    )

    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Mapper())
    startup_calls = len(calls)

    assert startup_calls > 0
    assert set(panel.pages) == {False, True}
    assert {False, True} <= set(calls)

    control_panel._set_control_panel_mode(panel, False)
    control_panel._set_control_panel_mode(panel, True)
    control_panel._set_control_panel_mode(panel, False)

    assert len(calls) == startup_calls


def test_control_panel_can_defer_page_builds(monkeypatch) -> None:
    from PySide6.QtWidgets import QWidget

    _qt_app()
    calls: list[bool] = []
    add_model_controls = control_panel._add_model_controls

    def wrapped_add_model_controls(
        parent: QWidget,
        data: BaseModel,
        option_controls: list[object],
        title: str | None = None,
        advanced: bool = True,
    ) -> None:
        calls.append(advanced)
        add_model_controls(parent, data, option_controls, title, advanced)

    monkeypatch.setattr(
        control_panel, '_add_model_controls', wrapped_add_model_controls
    )

    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Mapper(), build=False, eager_modes=False)

    assert calls == []
    assert panel.pages == {}

    panel.rebuild()
    assert set(panel.pages) == {True}
    assert set(calls) == {True}

    startup_calls = len(calls)
    panel.show_mode(False)
    panel.show_mode(True)
    panel.show_mode(False)

    assert set(panel.pages) == {False, True}
    assert len(calls) > startup_calls
    assert {False, True} <= set(calls)


def test_control_panel_sections_are_collapsible() -> None:
    from PySide6.QtWidgets import QToolButton, QWidget

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    button = next(
        button
        for button in panel.findChildren(QToolButton)
        if button.objectName() == 'control_section_disclosure'
        and button.text() == 'General'
    )
    section = button.parent()
    assert isinstance(section, QWidget)
    body = section.findChild(QWidget, 'control_section_body')
    assert body is not None

    assert not body.isHidden()

    button.click()

    assert body.isHidden()

    button.click()

    assert not body.isHidden()


def test_control_panel_restores_sections_and_scroll(tmp_path) -> None:
    from PySide6.QtWidgets import QToolButton, QWidget

    qt_app = _qt_app()
    app = App(gui=True)
    app.__dict__['global_config'] = GlobalConfig(
        control_panel_sections={'Sound.sound': False},
        control_panel_scroll=120,
        file=tmp_path / 'global.toml',
    )
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, app, app=app)
    page = panel.content.currentWidget()
    assert page is not None
    button = next(
        button
        for button in page.findChildren(QToolButton)
        if button.objectName() == 'control_section_disclosure'
        and button.text() == 'Sound'
    )
    body = button.parent().findChild(QWidget, 'control_section_body')
    assert body is not None
    panel.verticalScrollBar().setRange(0, 200)

    qt_app.processEvents()

    assert body.isHidden()
    assert panel.verticalScrollBar().value() == 120

    button.click()
    panel.verticalScrollBar().setValue(50)
    panel.save_state()

    saved = GlobalConfig.read(tmp_path / 'global.toml')
    assert saved.control_panel_sections['Sound.sound']
    assert saved.control_panel_scroll == 50


def test_control_panel_sections_show_section_presets() -> None:
    from PySide6.QtWidgets import QComboBox, QWidget

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    presets = [
        [menu.itemText(i) for i in range(menu.count())]
        for menu in panel.findChildren(QComboBox)
        if menu.objectName() == 'section_preset'
    ]

    assert any('white-notes' in menu for menu in presets)
    assert any('just-14' in menu for menu in presets)


def test_dials_are_limited_to_explicit_analog_controls(
    file_regression,
) -> None:
    _check_regression(
        file_regression,
        {
            'sound_gain': control_panel._numeric_metadata(Sound, 'gain').dial,
            'sound_minimum_note_time': control_panel._numeric_metadata(
                Sound, 'minimum_note_time'
            ).dial,
            'sound_note_offset': control_panel._numeric_metadata(
                Sound, 'note_offset'
            ).dial,
        },
    )


def test_numeric_fields_have_numeric_metadata() -> None:
    missing = [
        f'{cls.__name__}.{name}'
        for cls in _model_classes(Tuney())
        for name in cls.model_fields
        if _is_scalar_numeric_field(cls, name)
        and not any(
            isinstance(metadata, Numeric)
            for metadata in cls.model_fields[name].metadata
        )
    ]

    assert missing == []


def test_numeric_dial_values_use_dial_range() -> None:
    dial = Numeric(min=2, max=6)

    assert dial.spin_to_dial(4) == 50
    assert dial.dial_to_spin(50) == 4


def test_log_numeric_dial_values_are_exponential() -> None:
    dial = Numeric(min=1, max=100, log=True)

    assert dial.spin_to_dial(10) == 50
    assert dial.dial_to_spin(50) == 10


def test_log_numeric_values_require_positive_range() -> None:
    with pytest.raises(
        ValueError, match='Logarithmic dials require positive min and max'
    ):
        Numeric(log=True)


def test_numeric_dials_require_range() -> None:
    numeric = Numeric()

    assert numeric.min is None
    assert numeric.max is None
    with pytest.raises(ValueError, match='Numeric dials require min and max'):
        Numeric(dial=True)


def test_numeric_increment_is_absolute_or_percentage() -> None:
    assert Numeric(inc=2).step(10, 3) == 16
    assert Numeric(min=1, max=100, log=True, inc=10).step(100, -1) == pytest.approx(
        100 / 1.1
    )


def test_visible_field_names(file_regression) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            name: list(control_panel_visibility._visible_field_names(data))
            for name, data in [
                ('tuney', tuney),
                ('mapper', tuney.mapper),
                ('sound', tuney.sound),
                ('polyphony', tuney.sound.polyphony),
                ('device', tuney.device),
            ]
        },
    )


def test_control_panel_labels_fit_their_text() -> None:
    from PySide6.QtWidgets import (
        QLabel,
        QWidget,
    )

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())

    labels = [
        label
        for label in panel.findChildren(QLabel)
        if label.objectName() == 'control_label'
    ]

    assert labels
    for label in labels:
        assert label.minimumWidth() >= label.fontMetrics().horizontalAdvance(
            label.text()
        )


def test_numeric_spinbox_uses_numeric_range() -> None:
    from PySide6.QtWidgets import QDoubleSpinBox, QWidget

    _qt_app()
    tuney = Tuney()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, tuney)
    editors = [
        widget
        for widget in panel.findChildren(QDoubleSpinBox)
        if widget.objectName() == 'control_editor'
        and widget.minimum() == 0
        and widget.maximum() == 4
    ]

    assert editors


def test_note_number_spinboxes_use_musical_ranges() -> None:
    from PySide6.QtWidgets import QSpinBox, QWidget

    _qt_app()
    tuney = Tuney()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, tuney)

    ranges = {
        f'{type(data).__name__}.{name}': (w.minimum(), w.maximum())
        for w in panel.findChildren(QSpinBox)
        if (binding := control_panel.CONTROL_BINDINGS.get(w)) is not None
        for data, name, _ in [binding]
    }

    assert ranges['Mapper.offset'] == (-99, 99)
    assert ranges['Scale.offset'] == (-99, 99)
    assert ranges['Sound.note_offset'] == (-99, 99)
    assert ranges['Oscillator.key_scale_note'] == (0, 127)
    assert ranges['Tuning.root_note'] == (0, 127)


@pytest.mark.parametrize(
    ('cls', 'name', 'value'),
    [
        (Mapper, 'offset', 100),
        (Scale, 'offset', 100),
        (Sound, 'note_offset', 100),
        (Oscillator, 'key_scale_note', 128),
        (Tuning, 'root_note', 128),
    ],
)
def test_note_number_ranges_are_model_constraints(
    cls: type[BaseModel], name: str, value: int
) -> None:
    with pytest.raises(ValueError):
        cls(**{name: value})


def test_midi_enable_control_stays_enabled_when_midi_is_disabled() -> None:
    from PySide6.QtWidgets import QWidget

    _qt_app()
    midi = MidiOut(enable=False)
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, midi)

    cells = {
        name: widget
        for widget in panel.findChildren(QWidget)
        if (binding := control_panel.CONTROL_BINDINGS.get(widget)) is not None
        for data, name, _ in [binding]
        if data is midi
    }

    assert cells['enable'].isEnabled()
    assert not cells['name'].isEnabled()
    assert not cells['channel'].isEnabled()


def test_midi_input_enable_control_stays_enabled_when_midi_is_disabled() -> None:
    from PySide6.QtWidgets import QWidget

    _qt_app()
    midi = MIDIIn(enable=False)
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, midi)

    cells = {
        name: widget
        for widget in panel.findChildren(QWidget)
        if (binding := control_panel.CONTROL_BINDINGS.get(widget)) is not None
        for data, name, _ in [binding]
        if data is midi
    }

    assert cells['enable'].isEnabled()
    assert not cells['name'].isEnabled()
    assert not cells['channel'].isEnabled()


def test_numeric_spinboxes_use_modifier_steps(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    _qt_app()
    parent = QWidget()
    float_spin = control_panel._NumericDoubleSpinBox(parent, Numeric(inc=0.5))
    float_spin.setRange(-100, 100)
    float_spin.setValue(10)
    int_spin = control_panel._NumericSpinBox(parent)
    int_spin.setRange(-200, 200)
    int_spin.setSingleStep(10)
    int_spin.setValue(10)

    monkeypatch.setattr(
        control_panel_spin.QApplication,
        'keyboardModifiers',
        lambda: Qt.KeyboardModifier.ShiftModifier,
    )
    float_spin.stepBy(1)
    int_spin.stepBy(1)

    assert float_spin.value() == 15
    assert int_spin.value() == 110

    monkeypatch.setattr(
        control_panel_spin.QApplication,
        'keyboardModifiers',
        lambda: Qt.KeyboardModifier.AltModifier,
    )
    float_spin.stepBy(-1)
    int_spin.stepBy(-1)

    assert float_spin.value() == pytest.approx(14.95)
    assert int_spin.value() == 109


def test_control_panel_syncs_fixed_beginner_and_advanced_pages() -> None:
    from PySide6.QtWidgets import QSpinBox, QWidget

    _qt_app()
    mapper = Mapper()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, mapper)
    panel.show_mode(False)
    editors = [
        widget
        for widget in panel.findChildren(QSpinBox)
        if control_panel.CONTROL_BINDINGS.get(widget, (None,))[0] is mapper
        and control_panel.CONTROL_BINDINGS[widget][1] == 'range_limit'
    ]

    assert len(editors) == 2
    control_panel._set_model_value(mapper, 'range_limit', 24, editors[0])

    assert [editor.value() for editor in editors] == [24, 24]


def test_control_panel_language_menu_sets_mapper_alphabet() -> None:
    from PySide6.QtWidgets import QComboBox, QWidget

    _qt_app()
    mapper = Mapper()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, mapper)
    assert panel.content.currentWidget() is not None
    menus = [
        widget
        for widget in panel.content.currentWidget().findChildren(QComboBox)
        if widget.objectName() == 'alphabet_language'
    ]

    assert len(menus) == 1
    assert menus[0].itemText(0) == 'Language...'
    assert menus[0].itemText(1) == '(clear)'
    assert menus[0].itemText(2).startswith('🇨🇿 ')
    menus[0].setCurrentText('🇫🇷 French')

    assert mapper.alphabet is not None
    assert mapper.alphabet.startswith('ABCDEFGHIJKLMNOPQRSTUVWXYZÀÂ')
    assert 'ç' in mapper.alphabet
    assert menus[0].currentText() == 'Language...'

    menus[0].setCurrentText('(clear)')

    assert mapper.alphabet is None
    assert menus[0].currentText() == 'Language...'


def test_control_panel_rejects_empty_and_invalid_tunings() -> None:
    tuning = Tuning()

    with pytest.raises(ValueError, match='No frequency table configured'):
        control_panel._set_model_value(tuning, 'table', Table())
    with pytest.raises(ValueError, match='Bad expressions'):
        control_panel._set_model_value(tuning, 'ratios', Ratios(text='bad'))


def test_float_spinboxes_use_config_decimal_separator() -> None:
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QDoubleSpinBox, QWidget

    _qt_app()
    original = QLocale()
    QLocale.setDefault(QLocale(QLocale.Language.French, QLocale.Country.France))
    try:
        parent = QWidget()
        panel = control_panel.ControlPanel(parent, Tuney())
        spinboxes = [
            spinbox
            for spinbox in panel.findChildren(QDoubleSpinBox)
            if spinbox.objectName() == 'control_editor'
        ]

        assert spinboxes
        assert {spinbox.locale().decimalPoint() for spinbox in spinboxes} == {'.'}
        assert any('.' in spinbox.text() for spinbox in spinboxes)
    finally:
        QLocale.setDefault(original)


def test_large_seed_uses_text_entry_instead_of_spinbox() -> None:
    from PySide6.QtWidgets import QLineEdit, QSpinBox, QWidget

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, TextTimings(seed=2_615_033_043))

    assert not panel.findChildren(QSpinBox)
    assert any(
        entry.text() == '2615033043'
        for entry in panel.findChildren(QLineEdit)
        if entry.objectName() == 'control_editor'
    )


def test_ratio_fractions_are_serialized_for_text_entry() -> None:
    from PySide6.QtWidgets import QLineEdit, QWidget

    _qt_app()
    tuney = Tuney(tuning=Tuning(type=Type.ratios, ratios=Ratios(text='3/2')))
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, tuney)

    assert any(
        entry.text() == '3/2'
        for entry in panel.findChildren(QLineEdit)
        if entry.objectName() == 'control_editor'
    )


def test_tuning_expression_fields_use_semicolon_separated_expressions() -> None:
    assert control_panel._parse_entry_value(
        '3 / 2; cents(100)', object, None, 'ratios'
    ) == Ratios.from_strings(['3 / 2', 'cents(100)'])
    assert control_panel._parse_entry_value(
        '440; 880 / 2', object, None, 'table'
    ) == Table(text='440; 880 / 2')


def test_tuning_type_selects_visible_control_form() -> None:
    assert control_panel._visible_child_names(Tuning(), advanced=True) == ['computed']
    assert control_panel._visible_control_names(
        Tuning(type=Type.table, table=Table(text='440')), advanced=True
    ) == [
        'type',
        'detune',
        'root_frequency',
        'root_note',
        'table',
    ]
    assert control_panel._visible_control_names(
        Tuning(type=Type.ratios, ratios=Ratios(text='2')), advanced=True
    ) == [
        'type',
        'detune',
        'root_frequency',
        'root_note',
        'ratios',
    ]


def test_tuning_type_switches_stacked_form_without_rebuild(
    monkeypatch,
) -> None:
    from PySide6.QtWidgets import QRadioButton, QStackedWidget, QWidget

    def rebuild_parent_control_panel(parent: QWidget) -> None:
        raise AssertionError('tuning type changed by rebuilding the control panel')

    monkeypatch.setattr(
        control_panel, '_rebuild_parent_control_panel', rebuild_parent_control_panel
    )

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuning())
    stack = next(
        stack
        for stack in panel.findChildren(QStackedWidget)
        if stack.objectName() == 'tuning_form_stack'
    )
    table = next(
        radio for radio in panel.findChildren(QRadioButton) if radio.text() == 'table'
    )

    assert stack.currentWidget() is panel.findChild(QWidget, 'tuning_form_computed')

    table.click()

    assert stack.currentWidget() is panel.findChild(QWidget, 'tuning_form_table')
    assert panel.pages[True] is panel.content.currentWidget()


def test_scala_browser_navigates_existing_trie_nodes(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QWidget

    ratios = {
        'abc': Ratios(text='2', name='abc.scl', desc='first scale'),
        'abd': Ratios(text='3', name='abd.scl', desc='second scale'),
        'xyz': Ratios(text='4', name='xyz.scl', desc='third scale'),
    }
    monkeypatch.setattr(control_panel_scala, 'scala_trie', lambda: build_trie(ratios))

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None

    _press(browser, Qt.Key.Key_A, 'a')
    _press(browser, Qt.Key.Key_X, 'x')
    _press(browser, Qt.Key.Key_B, 'b')
    _press(browser, Qt.Key.Key_Down)

    assert browser.text() == 'abd'
    assert browser.selectionStart() == 2
    assert browser.selectedText() == 'd'
    assert browser.toolTip() == 'second scale'

    _press(browser, Qt.Key.Key_Down)
    assert browser.text() == 'abc'
    assert browser.selectedText() == 'c'
    assert browser.toolTip() == 'first scale'

    _press(browser, Qt.Key.Key_Left)
    _press(browser, Qt.Key.Key_Up)
    assert browser.text() == 'abc'
    assert browser.selectionStart() == 1

    _press(browser, Qt.Key.Key_Left)
    _press(browser, Qt.Key.Key_X, 'x')
    assert browser.text() == 'xyz'
    assert browser.selectionStart() == 1
    assert browser.selectedText() == 'yz'

    _press(browser, Qt.Key.Key_Down)
    assert browser.text() == 'xyz'
    assert browser.selectionStart() == 1

    _press(browser, Qt.Key.Key_Right)
    assert browser.cursorPosition() == 3

    _press(browser, Qt.Key.Key_Left)
    assert browser.selectionStart() == 2
    assert browser.selectedText() == 'z'


def test_scala_description_does_not_force_panel_width() -> None:
    from PySide6.QtWidgets import QLineEdit, QSizePolicy, QWidget

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    description = panel.findChild(QLineEdit, 'tuning_description')

    assert description is not None
    assert description.minimumWidth() == control_panel_sizing.MIN_EDITOR_WIDTH
    assert description.maximumWidth() == 120 * control_panel_sizing.ENTRY_CHAR_WIDTH
    assert description.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding


def test_scala_browser_auditions_completed_tuning(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QWidget

    ratios = Ratios(text='3/2', name='xyz.scl', desc='first scale')
    app = App(gui=True)
    original = app.tuning.model_copy(deep=True)
    closed = []
    app.__dict__['main_window'] = _FakeMainWindow()
    app.__dict__['player'] = _FakePlayer(closed)
    other_ratios = Ratios(text='2', name='xbc.scl', desc='second scale')
    monkeypatch.setattr(
        control_panel_scala,
        'scala_trie',
        lambda: build_trie({'abc': ratios, 'xbc': other_ratios}),
    )

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, app, app=app)
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None

    _press(browser, Qt.Key.Key_A, 'a')
    _press(browser, Qt.Key.Key_B, 'b')
    _press(browser, Qt.Key.Key_C, 'c')

    assert app.tuning.type == Type.ratios
    assert app.tuning.ratios == ratios
    assert closed == ['close']
    assert 'player' not in app.__dict__

    _press(browser, Qt.Key.Key_Left)

    assert app.tuning.model_dump() == original.model_dump()
    assert closed == ['close']


def test_scala_browser_loads_selected_tuning_with_undo(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QMessageBox, QWidget

    ratios = Ratios(text='3/2', name='abc.scl', desc='first scale')
    app = App(gui=True)
    app.__dict__['main_window'] = _FakeMainWindow()
    monkeypatch.setattr(
        control_panel_scala, 'scala_trie', lambda: build_trie({'abc': ratios})
    )
    monkeypatch.setattr(
        control_panel.QMessageBox,
        'question',
        lambda *_: QMessageBox.StandardButton.Yes,
    )

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, app, app=app)
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None
    name = panel.findChild(QLineEdit, 'tuning_name')
    description = panel.findChild(QLineEdit, 'tuning_description')
    assert name is not None
    assert description is not None

    _press(browser, Qt.Key.Key_A, 'a')
    _press(browser, Qt.Key.Key_B, 'b')
    _press(browser, Qt.Key.Key_C, 'c')
    assert name.text() == ''
    assert description.text() == ''
    _press(browser, Qt.Key.Key_Return)

    assert app.tuning.type == Type.ratios
    assert app.tuning.ratios == ratios
    assert app.main_window.history.undo_count == 1
    assert app.main_window.ui.rebuild_count == 1
    assert name.text() == 'abc'
    assert description.text() == 'first scale'


def test_scala_browser_data_is_lazy_loaded(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QWidget

    calls = []
    ratios = Ratios(text='3/2', name='abc.scl', desc='first scale')
    monkeypatch.setattr(
        control_panel_scala,
        'scala_trie',
        lambda: calls.append('load') or build_trie({'abc': ratios}),
    )

    _qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None
    assert calls == []

    _press(browser, Qt.Key.Key_A, 'a')

    assert calls == ['load']


def _press(widget, key: object, text: str = '') -> None:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    assert isinstance(key, Qt.Key)
    widget.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            key,
            Qt.KeyboardModifier.NoModifier,
            text,
        )
    )


class _FakeHistory:
    def __init__(self) -> None:
        self.undo_count = 0

    def checkpoint_undo(self) -> None:
        self.undo_count += 1


class _FakeUi:
    def __init__(self) -> None:
        self.rebuild_count = 0

    def rebuild_control_panel(self) -> None:
        self.rebuild_count += 1


class _FakeMainWindow:
    def __init__(self) -> None:
        self.history = _FakeHistory()
        self.ui = _FakeUi()


class _FakePlayer:
    def __init__(self, closed: list[str]) -> None:
        self.closed = closed

    def close(self) -> None:
        self.closed.append('close')
