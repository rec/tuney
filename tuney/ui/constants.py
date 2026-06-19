from collections.abc import Callable

from pydantic import BaseModel, Field

from ..audio.device import DType, device_names
from ..audio.midi import output_names as midi_output_names

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
    rows: list[list[str]] = Field(default_factory=list)


CONTROL_CONFIGS = {
    'Tuney': ControlConfig(
        hidden_fields=['config_file', 'text', 'cli'],
        general_fields=['max_gap', 'silent', 'run_in_background'],
    ),
    'MultiPlayer': ControlConfig(general_fields=['gain', 'note_offset']),
    'PitchToFrequency': ControlConfig(general_fields=['function']),
    'Device': ControlConfig(rows=[['samplerate', 'device', 'dtype']]),
    'Mapper': ControlConfig(
        rows=[['alphabet'], ['length', 'offset', 'case_sensitive', 'invert']]
    ),
    'Oscillator': ControlConfig(rows=[['waveform', 'period', 'duty_cycle']]),
    'Scale': ControlConfig(
        rows=[
            ['alphabet', 'root', 'begin', 'end', 'offset'],
            ['notes', 'intervals'],
        ]
    ),
    'TuningImpl': ControlConfig(
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
        ]
    ),
    'MIDI': ControlConfig(
        rows=[['enable', 'output', 'channel', 'velocity', 'note_offset']]
    ),
    'TextTimings': ControlConfig(
        rows=[
            ['space', 'period', 'comma', 'colon', 'semicolon', 'blank_line'],
            ['overlap', 'seed', 'alpha_only', 'strip_accents', 'scale'],
            ['other', 'timings'],
        ]
    ),
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
    'Device.device': device_names,
    'Device.dtype': lambda: [dtype.value for dtype in DType],
    'MIDI.output': midi_output_names,
}
DISABLED_CONTROL_FG_COLOR = 'gray88', 'gray42'
DISABLED_TEXT_COLOR = 'gray96', 'gray96'
