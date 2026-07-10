from collections.abc import Mapping, Sequence
from enum import Enum
from typing import get_origin

import pytest
import tomlkit
from pydantic import BaseModel
from pytest import MonkeyPatch
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.audio.device import Device
from tuney.audio.midi import MIDI
from tuney.audio.sound import Sound
from tuney.cfg.display import Numeric
from tuney.cfg.tuney import Tuney
from tuney.mapper.mapper import Mapper
from tuney.scale.ratios import Ratios
from tuney.scale.scale import Scale
from tuney.scale.table import Table
from tuney.scale.tuning import Tuning, Type
from tuney.time.text_timings import TextTimings
from tuney.ui import control_panel


def _check_regression(
    file_regression: FileRegressionFixture, actual: Mapping[str, object]
) -> None:
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


def _control_fields(data: BaseModel) -> list[str]:
    return [
        name
        for name in control_panel._visible_field_names(data)
        if not isinstance(getattr(data, name), BaseModel)
    ]


def _entry_width(cls: type[BaseModel], name: str) -> int | None:
    return control_panel._entry_width(
        name,
        cls.model_fields[name].annotation,
        control_panel._control_metadata(cls, name),
        control_panel._numeric_metadata(cls, name),
    )


def _is_scalar_numeric_field(cls: type[BaseModel], name: str) -> bool:
    annotation = cls.model_fields[name].annotation
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
    file_regression: FileRegressionFixture,
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


def test_set_model_value_converts_dtype_string(
    file_regression: FileRegressionFixture,
) -> None:
    device = Device()

    control_panel._set_model_value(device, 'dtype', 'int16')

    _check_regression(file_regression, {'dtype': device.dtype})


def test_set_model_value_notifies_device_change(
    file_regression: FileRegressionFixture,
) -> None:
    device = Device()
    changes: list[bool] = []
    device.set_change_callback(lambda: changes.append(True))

    control_panel._set_model_value(device, 'device', 'speaker')

    _check_regression(file_regression, {'changes': changes})


def test_scale_and_mapper_changes_schedule_note_grid_rebuild(
    file_regression: FileRegressionFixture,
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
    file_regression: FileRegressionFixture,
) -> None:
    _check_regression(
        file_regression,
        {
            'bad_notes': control_panel._scale_note_errors(Scale(notes='C frog D')),
            'good_notes': control_panel._scale_note_errors(Scale(notes='C D')),
        },
    )


def test_scale_has_note_buttons_rejects_non_positive_note_count(
    file_regression: FileRegressionFixture,
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
    file_regression: FileRegressionFixture,
) -> None:
    annotation = TextTimings.model_fields['timings'].annotation

    _check_regression(
        file_regression,
        {'value': control_panel._parse_entry_value('[1, 2]', annotation, None)},
    )


def test_parse_entry_value_keeps_intervals_as_text(
    file_regression: FileRegressionFixture,
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
    file_regression: FileRegressionFixture,
) -> None:
    annotation = Tuney.model_fields['text'].annotation

    _check_regression(
        file_regression,
        {'value': control_panel._parse_entry_value('hello', annotation, None)},
    )


def test_entry_width_uses_compact_numeric_widths(
    file_regression: FileRegressionFixture,
) -> None:
    _check_regression(
        file_regression,
        {
            'max_gap': _entry_width(Tuney, 'max_gap'),
            'gain': _entry_width(Sound, 'gain'),
            'scale': _entry_width(TextTimings, 'scale'),
            'frequency': _entry_width(Tuning, 'root_frequency'),
            'note': _entry_width(Tuning, 'root_note'),
            'device': _entry_width(Device, 'device'),
            'sample_rate': _entry_width(Device, 'sample_rate'),
            'space': _entry_width(TextTimings, 'space'),
            'root': _entry_width(Scale, 'root'),
            'output': _entry_width(MIDI, 'output'),
        },
    )


def test_display_labels_use_sentence_case() -> None:
    assert control_panel._display_label('text_timings') == 'Text timings'
    assert control_panel._display_label('sample_rate') == 'Sample rate'


def test_control_rows_use_compact_model_layouts(
    file_regression: FileRegressionFixture,
) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            'tuney': control_panel._control_rows(tuney, _control_fields(tuney)),
            'sound': control_panel._control_rows(
                tuney.sound, _control_fields(tuney.sound)
            ),
            'polyphony': control_panel._control_rows(
                tuney.sound.polyphony, _control_fields(tuney.sound.polyphony)
            ),
            'device': control_panel._control_rows(
                tuney.device, _control_fields(tuney.device)
            ),
            'mapper': control_panel._control_rows(
                tuney.mapper, _control_fields(tuney.mapper)
            ),
            'oscillator': control_panel._control_rows(
                tuney.sound.oscillator, _control_fields(tuney.sound.oscillator)
            ),
            'scale': control_panel._control_rows(
                tuney.scale, _control_fields(tuney.scale)
            ),
            'tuning': control_panel._control_rows(
                tuney.tuning, control_panel._visible_control_names(tuney.tuning)
            ),
            'computed': control_panel._control_rows(
                tuney.tuning.computed, _control_fields(tuney.tuning.computed)
            ),
            'midi': control_panel._control_rows(
                tuney.midi, _control_fields(tuney.midi)
            ),
            'text_timings': control_panel._control_rows(
                tuney.text_timings, _control_fields(tuney.text_timings)
            ),
        },
    )


def test_beginner_mode_filters_advanced_controls(
    file_regression: FileRegressionFixture,
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


def test_control_panel_reuses_mode_pages(monkeypatch: MonkeyPatch) -> None:
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
    panel = control_panel.ControlPanel(parent, Tuney())
    advanced_calls = len(calls)

    control_panel._set_control_panel_mode(panel, False)
    beginner_calls = len(calls)

    assert advanced_calls > 0
    assert beginner_calls > advanced_calls

    control_panel._set_control_panel_mode(panel, True)
    control_panel._set_control_panel_mode(panel, False)

    assert len(calls) == beginner_calls


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


def test_dials_are_limited_to_explicit_analog_controls(
    file_regression: FileRegressionFixture,
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


def test_visible_field_names(file_regression: FileRegressionFixture) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            name: list(control_panel._visible_field_names(data))
            for name, data in [
                ('tuney', tuney),
                ('mapper', tuney.mapper),
                ('sound', tuney.sound),
                ('polyphony', tuney.sound.polyphony),
                ('device', tuney.device),
            ]
        },
    )


def test_control_panel_labels_and_editors_keep_minimum_sizes() -> None:
    from PySide6.QtWidgets import (
        QComboBox,
        QDoubleSpinBox,
        QLabel,
        QLineEdit,
        QSpinBox,
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
    editors = [
        *[
            editor
            for editor in panel.findChildren(QLineEdit)
            if editor.objectName() == 'control_editor'
        ],
        *[
            editor
            for editor in panel.findChildren(QSpinBox)
            if editor.objectName() == 'control_editor'
        ],
        *[
            editor
            for editor in panel.findChildren(QDoubleSpinBox)
            if editor.objectName() == 'control_editor'
        ],
        *[
            editor
            for editor in panel.findChildren(QComboBox)
            if editor.objectName() == 'control_editor'
        ],
    ]

    assert labels
    assert editors
    for label in labels:
        assert label.minimumWidth() >= label.fontMetrics().horizontalAdvance(
            label.text()
        )
    for editor in editors:
        assert editor.minimumWidth() >= control_panel.MIN_EDITOR_WIDTH


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
    monkeypatch: MonkeyPatch,
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
