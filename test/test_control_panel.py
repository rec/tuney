from collections.abc import Mapping, Sequence
from enum import Enum

import tomlkit
from pydantic import BaseModel
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.audio.device import Device
from tuney.mapper.mapper import Mapper
from tuney.scale.scale import Scale
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney
from tuney.ui.control_panel import (
    _control_rows,
    _entry_width,
    _parse_entry_value,
    _rebuild_note_grid_if_mapping_changed,
    _scale_has_note_buttons,
    _scale_note_errors,
    _set_model_value,
    _uses_dial,
    _visible_child_names,
    _visible_control_names,
    _visible_field_names,
)


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
        for name in _visible_field_names(data)
        if not isinstance(getattr(data, name), BaseModel)
    ]


def test_set_model_value_validates_and_clears_cached_values(
    file_regression: FileRegressionFixture,
) -> None:
    mapper = Mapper()
    before = mapper.char_to_number['b']

    _set_model_value(mapper, 'length', '1')

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
    tuney = Tuney()

    _set_model_value(tuney.player.device, 'dtype', 'int16')

    _check_regression(file_regression, {'dtype': tuney.player.device.dtype})


def test_set_model_value_notifies_device_change(
    file_regression: FileRegressionFixture,
) -> None:
    device = Device()
    changes: list[bool] = []
    device.set_change_callback(lambda: changes.append(True))

    _set_model_value(device, 'device', 'speaker')

    _check_regression(file_regression, {'changes': changes})


def test_scale_and_mapper_changes_schedule_note_grid_rebuild(
    file_regression: FileRegressionFixture,
) -> None:
    scheduled: list[tuple[int, object, tuple[object, ...]]] = []

    class Parent:
        def after(self, delay: int, callback: object, *args: object) -> None:
            scheduled.append((delay, callback, args))

    parent = Parent()

    _rebuild_note_grid_if_mapping_changed(parent, Scale())
    _rebuild_note_grid_if_mapping_changed(parent, Mapper())

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
            'bad_notes': _scale_note_errors(Scale(notes='C frog D')),
            'good_notes': _scale_note_errors(Scale(notes='C D')),
        },
    )


def test_scale_has_note_buttons_rejects_non_positive_note_count(
    file_regression: FileRegressionFixture,
) -> None:
    _check_regression(
        file_regression,
        {
            'default': _scale_has_note_buttons(Scale()),
            'zero_interval': _scale_has_note_buttons(Scale(intervals=[0])),
        },
    )


def test_parse_entry_value_parses_optional_lists_as_json(
    file_regression: FileRegressionFixture,
) -> None:
    annotation = TextTimings.model_fields['timings'].annotation

    _check_regression(
        file_regression,
        {'value': _parse_entry_value('[1, 2]', annotation, None)},
    )


def test_parse_entry_value_keeps_intervals_as_text(
    file_regression: FileRegressionFixture,
) -> None:
    annotation = Scale.model_fields['intervals'].annotation

    _check_regression(
        file_regression,
        {'value': _parse_entry_value('221 2221', annotation, [2], 'intervals')},
    )


def test_parse_entry_value_keeps_text_as_text(
    file_regression: FileRegressionFixture,
) -> None:
    annotation = Tuney.model_fields['text'].annotation

    _check_regression(
        file_regression,
        {'value': _parse_entry_value('hello', annotation, None)},
    )


def test_entry_width_uses_compact_numeric_widths(
    file_regression: FileRegressionFixture,
) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            'max_gap': _entry_width(
                'max_gap', Tuney.model_fields['max_gap'].annotation
            ),
            'gain': _entry_width(
                'gain', type(tuney.player).model_fields['gain'].annotation
            ),
            'scale': _entry_width(
                'scale', type(tuney.text_timings).model_fields['scale'].annotation
            ),
            'period': _entry_width(
                'period',
                type(tuney.player.oscillator).model_fields['period'].annotation,
            ),
            'root_frequency': _entry_width(
                'root_frequency',
                type(tuney.player.scale.tuning)
                .model_fields['root_frequency']
                .annotation,
            ),
            'root_note': _entry_width(
                'root_note',
                type(tuney.player.scale.tuning).model_fields['root_note'].annotation,
            ),
            'device': _entry_width(
                'device', type(tuney.player.device).model_fields['device'].annotation
            ),
            'samplerate': _entry_width(
                'samplerate',
                type(tuney.player.device).model_fields['samplerate'].annotation,
                'Device',
            ),
            'space': _entry_width(
                'space',
                type(tuney.text_timings).model_fields['space'].annotation,
                'TextTimings',
            ),
            'root': _entry_width(
                'root',
                type(tuney.player.scale).model_fields['root'].annotation,
                'Scale',
            ),
            'output': _entry_width(
                'output',
                type(tuney.midi).model_fields['output'].annotation,
                'MIDI',
            ),
        },
    )


def test_control_rows_use_compact_model_layouts(
    file_regression: FileRegressionFixture,
) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            'tuney': _control_rows(tuney, _control_fields(tuney)),
            'player': _control_rows(tuney.player, _control_fields(tuney.player)),
            'device': _control_rows(
                tuney.player.device, _control_fields(tuney.player.device)
            ),
            'mapper': _control_rows(tuney.mapper, _control_fields(tuney.mapper)),
            'oscillator': _control_rows(
                tuney.player.oscillator, _control_fields(tuney.player.oscillator)
            ),
            'scale': _control_rows(
                tuney.player.scale, _control_fields(tuney.player.scale)
            ),
            'tuning': _control_rows(
                tuney.player.scale.tuning, _control_fields(tuney.player.scale.tuning)
            ),
            'midi': _control_rows(tuney.midi, _control_fields(tuney.midi)),
            'text_timings': _control_rows(
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
            'mapper_controls': _visible_control_names(tuney.mapper, advanced=False),
            'tuney_children': _visible_child_names(tuney, advanced=False),
            'tuney_controls': _visible_control_names(tuney, advanced=False),
        },
    )


def test_dials_are_limited_to_explicit_analog_controls(
    file_regression: FileRegressionFixture,
) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            'player_gain': _uses_dial(tuney.player, 'gain'),
            'oscillator_period': _uses_dial(tuney.player.oscillator, 'period'),
            'player_minimum_note_time': _uses_dial(tuney.player, 'minimum_note_time'),
            'player_note_offset': _uses_dial(tuney.player, 'note_offset'),
        },
    )


def test_visible_field_names(file_regression: FileRegressionFixture) -> None:
    tuney = Tuney()

    _check_regression(
        file_regression,
        {
            name: list(_visible_field_names(data))
            for name, data in [
                ('tuney', tuney),
                ('mapper', tuney.mapper),
                ('player', tuney.player),
                ('device', tuney.player.device),
            ]
        },
    )
