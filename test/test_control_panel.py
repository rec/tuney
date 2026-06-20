import tomlkit
from pydantic import BaseModel
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.audio.device import Device, DType
from tuney.mapper.mapper import Mapper
from tuney.scale.scale import Scale
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney
from tuney.ui.control_panel import (
    _control_rows,
    _entry_width,
    _parse_entry_value,
    _rebuild_note_grid_if_scale_changed,
    _scale_has_note_buttons,
    _scale_note_errors,
    _set_model_value,
    _visible_field_names,
)


def _control_fields(data: BaseModel) -> list[str]:
    return [
        name
        for name in _visible_field_names(data)
        if not isinstance(getattr(data, name), BaseModel)
    ]


def test_set_model_value_validates_and_clears_cached_values():
    mapper = Mapper()
    assert mapper.char_to_number['b'] == 1

    _set_model_value(mapper, 'length', '1')

    assert mapper.length == 1
    assert mapper.char_to_number['b'] == 0


def test_set_model_value_converts_dtype_string():
    tuney = Tuney()

    _set_model_value(tuney.player.device, 'dtype', 'int16')

    assert tuney.player.device.dtype == DType.int16


def test_set_model_value_notifies_device_change():
    device = Device()
    changes: list[bool] = []
    device.set_change_callback(lambda: changes.append(True))

    _set_model_value(device, 'device', 'speaker')

    assert changes == [True]


def test_scale_changes_schedule_note_grid_rebuild() -> None:
    scheduled: list[object] = []

    class Parent:
        def after(self, delay: int, callback: object, *args: object) -> None:
            scheduled.append((delay, callback, args))

    parent = Parent()

    _rebuild_note_grid_if_scale_changed(parent, Scale())
    _rebuild_note_grid_if_scale_changed(parent, Mapper())

    assert len(scheduled) == 1
    assert scheduled[0][0] == 0


def test_scale_note_errors_report_bad_notes_without_failing() -> None:
    assert _scale_note_errors(Scale(notes='C frog D')) == ['frog']
    assert _scale_note_errors(Scale(notes='C D')) == []


def test_scale_has_note_buttons_rejects_non_positive_note_count() -> None:
    assert _scale_has_note_buttons(Scale())
    assert not _scale_has_note_buttons(Scale(intervals=[0]))


def test_parse_entry_value_parses_optional_lists_as_json():
    annotation = TextTimings.model_fields['timings'].annotation

    assert _parse_entry_value('[1, 2]', annotation, None) == [1, 2]


def test_parse_entry_value_keeps_text_as_text():
    annotation = Tuney.model_fields['text'].annotation

    assert _parse_entry_value('hello', annotation, None) == 'hello'


def test_entry_width_uses_compact_numeric_widths():
    tuney = Tuney()

    assert _entry_width('max_gap', Tuney.model_fields['max_gap'].annotation) == 40
    assert (
        _entry_width('gain', type(tuney.player).model_fields['gain'].annotation) == 40
    )
    assert (
        _entry_width('scale', type(tuney.text_timings).model_fields['scale'].annotation)
        == 40
    )
    assert (
        _entry_width(
            'period', type(tuney.player.oscillator).model_fields['period'].annotation
        )
        == 60
    )
    assert (
        _entry_width(
            'root_frequency',
            type(tuney.player.scale.tuning).model_fields['root_frequency'].annotation,
        )
        == 60
    )
    assert (
        _entry_width(
            'root_note',
            type(tuney.player.scale.tuning).model_fields['root_note'].annotation,
        )
        == 40
    )
    assert (
        _entry_width(
            'device', type(tuney.player.device).model_fields['device'].annotation
        )
        is None
    )
    assert (
        _entry_width(
            'samplerate',
            type(tuney.player.device).model_fields['samplerate'].annotation,
            'Device',
        )
        == 60
    )
    assert (
        _entry_width(
            'space',
            type(tuney.text_timings).model_fields['space'].annotation,
            'TextTimings',
        )
        == 50
    )
    assert (
        _entry_width(
            'root',
            type(tuney.player.scale).model_fields['root'].annotation,
            'Scale',
        )
        == 10
    )
    assert (
        _entry_width(
            'output',
            type(tuney.midi).model_fields['output'].annotation,
            'MIDI',
        )
        == 120
    )


def test_control_rows_use_compact_model_layouts():
    tuney = Tuney()

    assert _control_rows(tuney, _control_fields(tuney)) == []
    assert _control_rows(tuney.player.device, _control_fields(tuney.player.device)) == [
        ['samplerate', 'device', 'dtype']
    ]
    assert _control_rows(tuney.mapper, _control_fields(tuney.mapper)) == [
        ['alphabet'],
        ['length', 'offset', 'case_sensitive', 'invert'],
    ]
    assert _control_rows(
        tuney.player.oscillator, _control_fields(tuney.player.oscillator)
    ) == [['waveform', 'period', 'duty_cycle']]
    assert _control_rows(tuney.player.scale, _control_fields(tuney.player.scale)) == [
        ['alphabet', 'root', 'begin', 'end', 'offset'],
        ['notes', 'intervals'],
    ]
    assert _control_rows(
        tuney.player.scale.tuning, _control_fields(tuney.player.scale.tuning)
    ) == [
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
    ]
    assert _control_rows(tuney.midi, _control_fields(tuney.midi)) == [
        ['enable', 'output', 'channel', 'velocity', 'note_offset']
    ]
    assert _control_rows(tuney.text_timings, _control_fields(tuney.text_timings)) == [
        ['space', 'period', 'comma', 'colon', 'semicolon', 'blank_line'],
        ['overlap', 'seed', 'alpha_only', 'strip_accents', 'scale'],
        ['other', 'timings'],
    ]


def test_visible_field_names(file_regression: FileRegressionFixture):
    tuney = Tuney()

    actual = {
        name: list(_visible_field_names(data))
        for name, data in [
            ('tuney', tuney),
            ('mapper', tuney.mapper),
            ('player', tuney.player),
            ('device', tuney.player.device),
        ]
    }

    file_regression.check(tomlkit.dumps(actual), extension='.toml')
