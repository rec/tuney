from __future__ import annotations

import re

from ..types import NoteNumber
from . import scale

# Standard: 60 = C3, C-1 == 0 Yamaha: 60 = C4, C0 == 0
A440 = 69

MIDI_ZERO_OCTAVE = -1
ACCIDENTAL_DICT = {'#': '♯', 'b': '♭', '♭': '♭', '♯': '♯'}
ACCIDENTALS = '#b♭♯'
FLAT, SHARP = '♭', '♯'
CANONICALS = FLAT + SHARP
NAME_TO_NUMBER = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
NAMES = ''.join(NAME_TO_NUMBER)
NUMBER_TO_NAME = {
    FLAT: ('C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'),
    SHARP: ('C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'),
}
NOTE_RE = re.compile(rf'([{NAMES}])([{ACCIDENTALS}]*)(-?\d*)')

assert ACCIDENTALS == ''.join(sorted(ACCIDENTAL_DICT))
assert CANONICALS == ACCIDENTALS[2:]


def tuning(note_number: NoteNumber) -> float:
    return 440.0 * 2 ** ((note_number - A440) / 12)


def to_number(name: str) -> int:
    if not (m := NOTE_RE.match(name)):
        raise ValueError(f'Cannot understand note {name}')

    name_, accidentals, octave = m.groups()
    semitones = sum(2 * (ACCIDENTAL_DICT[a] == SHARP) - 1 for a in accidentals)
    octaves = int(octave) - MIDI_ZERO_OCTAVE
    return 12 * octaves + NAME_TO_NUMBER[name_] + semitones


def to_name(note_number: NoteNumber, use_sharp: bool = True) -> str:
    accidental = SHARP if use_sharp else FLAT
    assert accidental in NUMBER_TO_NAME, accidental
    octave, number1 = divmod(note_number, 12)
    octave += MIDI_ZERO_OCTAVE
    name = NUMBER_TO_NAME[accidental][number1]
    return f'{name}{octave}'


assert isinstance(tuning, scale.Tuning)
assert isinstance(to_number, scale.ToNumber)
assert isinstance(to_name, scale.ToName)
