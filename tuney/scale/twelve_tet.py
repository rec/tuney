from __future__ import annotations

import re

from .scale import NoteNumber, Scale

A4 = 69


def tuning(note_number: NoteNumber) -> float:
    return 440.0 * 2 ** ((note_number - A4) / 12)


def name_to_number(name: str) -> int:
    from .. import note

    return note.Note.from_name(name).note_number


def number_to_name(number: NoteNumber, use_sharp: bool = True) -> str:
    from .. import note

    accidental = SHARP if use_sharp else FLAT
    return str(note.Note.from_note_number(number, accidental))


TWELVE_TET = Scale(tuning, name_to_number, number_to_name)

MIDI_ZERO_OCTAVE = -1
ACCIDENTAL_DICT = {"#": "♯", "b": "♭", "♭": "♭", "♯": "♯"}
ACCIDENTALS = "#b♭♯"
FLAT, SHARP = "♭", "♯"
CANONICALS = FLAT + SHARP
NOTE_TO_NUMBER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NUMBER_TO_NOTES = {
    FLAT: ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"),
    SHARP: ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"),
}
NOTE_RE = re.compile(rf"([A-G])([{ACCIDENTALS}]*)(-?\d*)")

assert ACCIDENTALS == "".join(sorted(ACCIDENTAL_DICT))
assert CANONICALS == ACCIDENTALS[2:]
