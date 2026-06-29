from collections.abc import Callable

from pydantic import BaseModel, Field

from ..audio.device import DType, device_names
from ..audio.midi import output_names as midi_output_names
from ..presets import preset_names

PAD = 16
QUARTER = PAD // 4

FONT = 'Arial', 12
TITLE_FONT = 'Arial', 13, 'bold'
CHECKBOX_SIZE = 14
RADIO_SIZE = 14
TOGGLE_HEIGHT = 18
ENTRY_CHAR_WIDTH = 10
SMALL_FLOAT_FIELDS = {'max_gap', 'gain', 'scale'}


class ControlConfig(BaseModel, frozen=True):
    hidden_fields: list[str] = Field(default_factory=list)
    general_fields: list[str] = Field(default_factory=list)
    beginner_fields: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


CONTROL_CONFIGS = {
    'Tuney': ControlConfig(
        hidden_fields=[
            'config_file',
            'text',
            'text_args',
            'backspace_repeat_delay',
            'backspace_repeat_rate',
            'gui',
            'output',
            'autosave_file',
        ],
        general_fields=[
            'preset',
            'max_gap',
            'hover_time',
            'silent',
            'run_in_background',
        ],
        beginner_fields=['preset', 'max_gap', 'silent'],
    ),
    'MultiPlayer': ControlConfig(
        general_fields=['gain', 'note_offset'],
        beginner_fields=['gain', 'note_offset', 'minimum_note_time'],
        rows=[['minimum_note_time', 'polyphonic_headroom', 'max_polyphony']],
    ),
    'PitchToFrequency': ControlConfig(
        general_fields=['function'], beginner_fields=['function']
    ),
    'Device': ControlConfig(
        beginner_fields=['samplerate', 'device'],
        rows=[['samplerate', 'device', 'dtype']],
    ),
    'Mapper': ControlConfig(
        beginner_fields=[
            'alphabet',
            'length',
            'offset',
            'range_limit',
            'limiter',
        ],
        rows=[
            ['alphabet'],
            ['length', 'offset', 'range_limit', 'limiter', 'case_sensitive', 'invert'],
        ],
    ),
    'Oscillator': ControlConfig(
        beginner_fields=['waveform', 'period', 'duty_cycle'],
        rows=[['waveform', 'period', 'duty_cycle', 'key_scale_note', 'key_scale']],
    ),
    'Scale': ControlConfig(
        beginner_fields=[
            'alphabet',
            'root',
            'begin',
            'end',
            'notes',
            'intervals',
            'accidentals',
        ],
        rows=[
            ['alphabet', 'root', 'begin', 'end', 'offset'],
            ['notes', 'intervals', 'accidentals'],
        ],
    ),
    'TuningImpl': ControlConfig(
        beginner_fields=[
            'detune',
            'notes_per_octave',
            'octave_ratio',
            'root_frequency',
            'root_note',
        ],
        rows=[
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
        ],
    ),
    'MIDI': ControlConfig(
        beginner_fields=['enable', 'output'],
        rows=[['enable', 'output', 'channel', 'velocity', 'note_offset']],
    ),
    'TextTimings': ControlConfig(
        beginner_fields=['space', 'period', 'comma', 'overlap', 'scale'],
        rows=[
            ['space', 'period', 'comma', 'colon', 'semicolon', 'blank_line'],
            ['overlap', 'seed', 'alpha_only', 'strip_accents', 'scale'],
            ['other', 'timings'],
        ],
    ),
}

DIAL_FIELDS = {
    'MultiPlayer.gain',
    'Oscillator.period',
    'Oscillator.duty_cycle',
}

ENTRY_WIDTHS = {
    'Device.samplerate': 6,
    'MIDI.output': 12,
    'Scale.root': 1,
    'Scale.begin': 1,
    'Scale.end': 1,
    'TextTimings.space': 5,
    'TextTimings.period': 5,
    'TextTimings.comma': 5,
    'TextTimings.colon': 5,
    'TextTimings.semicolon': 5,
    'TextTimings.blank_line': 5,
}
OPTION_VALUES: dict[str, Callable[[], list[str]]] = {
    'Tuney.preset': preset_names,
    'Device.device': device_names,
    'Device.dtype': lambda: [dtype.value for dtype in DType],
    'MIDI.output': midi_output_names,
}
DISABLED_CONTROL_FG_COLOR = 'gray88', 'gray42'
DISABLED_TEXT_COLOR = 'gray96', 'gray96'
