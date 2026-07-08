from collections.abc import Mapping, Sequence
from enum import Enum

import tomlkit
from pydantic import BaseModel
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.audio.device import Device
from tuney.audio.midi import MIDI
from tuney.audio.oscillator import Oscillator
from tuney.audio.sound import Sound
from tuney.display import Dial
from tuney.mapper.mapper import Mapper
from tuney.scale.root import Root
from tuney.scale.scale import Scale
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney
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


def _qt_app() -> object:
    from PySide6.QtWidgets import QApplication

    if (app := QApplication.instance()) is None:
        app = QApplication([])
    return app


def test_set_model_value_validates_and_clears_cached_values(
    file_regression: FileRegressionFixture,
) -> None:
    mapper = Mapper()
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
            'max_gap': control_panel._entry_width(
                'max_gap',
                Tuney.model_fields['max_gap'].annotation,
                control_panel._control_metadata(Tuney, 'max_gap'),
            ),
            'gain': control_panel._entry_width(
                'gain',
                Sound.model_fields['gain'].annotation,
                control_panel._control_metadata(Sound, 'gain'),
            ),
            'scale': control_panel._entry_width(
                'scale',
                TextTimings.model_fields['scale'].annotation,
                control_panel._control_metadata(TextTimings, 'scale'),
            ),
            'period': control_panel._entry_width(
                'period',
                Oscillator.model_fields['period'].annotation,
                control_panel._control_metadata(Oscillator, 'period'),
            ),
            'frequency': control_panel._entry_width(
                'frequency',
                Root.model_fields['frequency'].annotation,
                control_panel._control_metadata(Root, 'frequency'),
            ),
            'note': control_panel._entry_width(
                'note',
                Root.model_fields['note'].annotation,
                control_panel._control_metadata(Root, 'note'),
            ),
            'device': control_panel._entry_width(
                'device',
                Device.model_fields['device'].annotation,
                control_panel._control_metadata(Device, 'device'),
            ),
            'sample_rate': control_panel._entry_width(
                'sample_rate',
                Device.model_fields['sample_rate'].annotation,
                control_panel._control_metadata(Device, 'sample_rate'),
            ),
            'space': control_panel._entry_width(
                'space',
                TextTimings.model_fields['space'].annotation,
                control_panel._control_metadata(TextTimings, 'space'),
            ),
            'root': control_panel._entry_width(
                'root',
                Scale.model_fields['root'].annotation,
                control_panel._control_metadata(Scale, 'root'),
            ),
            'output': control_panel._entry_width(
                'output',
                MIDI.model_fields['output'].annotation,
                control_panel._control_metadata(MIDI, 'output'),
            ),
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
                tuney.tuning, _control_fields(tuney.tuning)
            ),
            'root': control_panel._control_rows(
                tuney.tuning.root, _control_fields(tuney.tuning.root)
            ),
            'computed': control_panel._control_rows(
                tuney.tuning.tuning, _control_fields(tuney.tuning.tuning)
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


def test_dials_are_limited_to_explicit_analog_controls(
    file_regression: FileRegressionFixture,
) -> None:
    _check_regression(
        file_regression,
        {
            'sound_gain': control_panel._dial_metadata(Sound, 'gain') is not None,
            'oscillator_period': control_panel._dial_metadata(Oscillator, 'period')
            is not None,
            'sound_minimum_note_time': control_panel._dial_metadata(
                Sound, 'minimum_note_time'
            )
            is not None,
            'sound_note_offset': control_panel._dial_metadata(Sound, 'note_offset')
            is not None,
        },
    )


def test_dial_values_use_dial_range() -> None:
    dial = Dial(min=2, max=6)

    assert dial.spin_to_dial(4) == 50
    assert dial.dial_to_spin(50) == 4


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
