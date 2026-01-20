from __future__ import annotations


from typing import Any, override

from . import NoteNumber, scale
from .. import note


class TwelveTET(scale.Scale):
    @override
    def number_to_frequency(self, note_number: NoteNumber) -> float:
        return 440.0 * 2 ** ((note_number - note.A4) / 12)


class Alphabet(scale.NoteNamer):
    def to_number(self, name: str) -> int:
        return note.Note.from_name(name).note_number

    @override
    def to_name(self, number: NoteNumber, **kwargs: Any) -> str:
        return self._to_name(number, **kwargs)

    def _to_name(
        self,
        number: NoteNumber,
        use_sharp: bool = True,
        use_unicode: bool = True,
    ) -> str:
        accidental = note.SHARP if use_sharp else note.FLAT
        return str(note.Note.from_note_number(number, accidental))
