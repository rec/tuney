import tomlkit
from pydantic import BaseModel
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.mapper.mapper import Mapper
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney
from tuney.ui.control_panel import (
    _control_rows,
    _entry_width,
    _parse_entry_value,
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

    assert _control_rows(tuney, _control_fields(tuney)) == [
        ['max_gap', 'disable_sound', 'run_in_background']
    ]
    assert _control_rows(tuney.mapper, _control_fields(tuney.mapper)) == [
        ['alphabet'],
        ['length', 'case_sensitive', 'invert', 'offset'],
    ]
    assert _control_rows(
        tuney.player.oscillator, _control_fields(tuney.player.oscillator)
    ) == [['waveform', 'period', 'duty_cycle']]
    assert _control_rows(
        tuney.player.scale.tuning, _control_fields(tuney.player.scale.tuning)
    ) == [
        [
            'detune',
            'limit_denominator',
            'octave_divisions',
            'octave_change',
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
        ['overlap', 'random_seed', 'alpha_only', 'strip_accents', 'scale'],
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
