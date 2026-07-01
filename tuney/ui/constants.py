from collections.abc import Callable

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
    'TextTimings.dot': 5,
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
