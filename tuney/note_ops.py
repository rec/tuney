from __future__ import annotations

import dataclasses as dc
from typing import Iterator

from .note import Note, NoteOctave


@dc.dataclass(frozen=True)
class NoteNumberer:
    semitone_offset: int = 0

    # C-1 is MIDI zero; use 0 for Yamaha where C0 is MIDI zero
    zero_octave: int = -1

    def __call__(self, n: NoteOctave) -> int:
        return n.note_number - self.zero_octave * 12 + self.semitone_offset


@dc.dataclass(frozen=True)
class Clamp:
    floor: int | None = None
    ceiling: int | None = None

    def __call__(self, n: NoteOctave) -> NoteOctave:
        d = n.note_number
        if self.floor is not None and self.floor > d:
            dc.replace(n, octave=1 + (self.floor - d) // 12)
        if self.ceiling is not None and d > self.ceiling:
            return dc.replace(n, octave=-(1 + (d - self.ceiling) // 12))
        return n


@dc.dataclass(frozen=True)
class Resolve:
    default_octave: int = 4

    def __call__(self, notes: Iterator[Note]) -> Iterator[NoteOctave]:
        previous: NoteOctave | None = None

        def resolve(note: Note) -> NoteOctave:
            if isinstance(note, NoteOctave):
                return note
            if previous is None:
                return NoteOctave(octave=self.default_octave, **dc.asdict(note))
            return previous.closest(note)

        for note in notes:
            yield (previous := resolve(note))
