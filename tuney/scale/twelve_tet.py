from __future__ import annotations


from .scale import NoteNumber, Scale
from .. import note


def tuning(note_number: NoteNumber) -> float:
    return 440.0 * 2 ** ((note_number - note.A4) / 12)


def name_to_number(name: str) -> int:
    return note.Note.from_name(name).note_number


def number_to_name(number: NoteNumber, use_sharp: bool = True) -> str:
    accidental = note.SHARP if use_sharp else note.FLAT
    return str(note.Note.from_note_number(number, accidental))


TWELVE_TET = Scale(tuning, name_to_number, number_to_name)
