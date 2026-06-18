from collections.abc import Callable

from ..audio.device import dtype_names, output_device_names
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
GUI_HIDDEN_FIELDS = {'Tuney': {'config_file', 'text', 'disable_gui'}}
GENERAL_HIDDEN_FIELDS = {
    'Tuney': {'max_gap', 'disable_sound', 'run_in_background'},
    'MultiPlayer': {'gain', 'note_offset'},
    'PitchToFrequency': {'function'},
}
CONTROL_ROWS = {
    'Device': [['samplerate', 'device', 'dtype']],
    'Mapper': [['alphabet'], ['length', 'offset', 'case_sensitive', 'invert']],
    'Oscillator': [['waveform', 'period', 'duty_cycle']],
    'Scale': [
        ['alphabet', 'root', 'begin', 'end', 'offset'],
        ['notes', 'intervals'],
    ],
    'TuningImpl': [
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
    'MIDI': [['enable', 'output', 'channel', 'velocity', 'note_offset']],
    'TextTimings': [
        ['space', 'period', 'comma', 'colon', 'semicolon', 'blank_line'],
        ['overlap', 'seed', 'alpha_only', 'strip_accents', 'scale'],
        ['other', 'timings'],
    ],
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
    'Device.device': output_device_names,
    'Device.dtype': dtype_names,
    'MIDI.output': midi_output_names,
}
DISABLED_CONTROL_FG_COLOR = 'gray88', 'gray42'
DISABLED_TEXT_COLOR = 'gray96', 'gray96'
