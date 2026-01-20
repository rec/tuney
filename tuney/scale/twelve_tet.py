from __future__ import annotations


from .scale import NamedScale, NoteNumber
from .. import note


def scale(note_number: NoteNumber) -> float:
    return 440.0 * 2 ** ((note_number - note.A4) / 12)


def name_to_number(name: str) -> int:
    return note.Note.from_name(name).note_number


def number_to_name(number: NoteNumber, use_sharp: bool = True) -> str:
    accidental = note.SHARP if use_sharp else note.FLAT
    return str(note.Note.from_note_number(number, accidental))


TWELVE_TET = NamedScale(scale, name_to_number, number_to_name)
