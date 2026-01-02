from __future__ import annotations

import dataclasses as dc
from typing import Iterator

from .note import Note, NoteOctave


@dc.dataclass(frozen=True)
class Clamp:
    floor: int | None = None
    ceiling: int | None = None

    def __call__(self, n: NoteOctave) -> NoteOctave:
        if self.floor is not None and self.floor > n.note_number:
            n = dc.replace(n, octave=1 + (self.floor - n.note_number) // 12)
        if self.ceiling is not None and n.note_number > self.ceiling:
            n = dc.replace(n, octave=-(1 + (n.note_number - self.ceiling) // 12))
        return n


@dc.dataclass(frozen=True)
class Resolve:
    default_octave: int = 4

    def __call__(self, notes: Iterator[Note]) -> Iterator[NoteOctave]:
        prev: NoteOctave | None = None
        for note in notes:
            if isinstance(note, NoteOctave):
                yield (prev := note)
            elif prev is None:
                yield (
                    prev := NoteOctave(octave=self.default_octave, **dc.asdict(note))
                )
            else:
                yield (prev := prev.closest(note))
