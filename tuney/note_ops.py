from __future__ import annotations

import dataclasses as dc
from typing import Iterator

from .note import NoteName, Note


@dc.dataclass(frozen=True)
class Clamp:
    floor: int | None = None
    ceiling: int | None = None

    def __call__(self, n: Note) -> Note:
        if self.floor is not None and self.floor > n.note_number:
            n = dc.replace(n, octave=1 + (self.floor - n.note_number) // 12)
        if self.ceiling is not None and n.note_number > self.ceiling:
            n = dc.replace(n, octave=-(1 + (n.note_number - self.ceiling) // 12))
        return n


@dc.dataclass(frozen=True)
class Resolve:
    default_octave: int = 4

    def __call__(self, notes: Iterator[NoteName]) -> Iterator[Note]:
        prev: Note | None = None
        for note in notes:
            if isinstance(note, Note):
                prev = note
            elif prev is None:
                prev = Note(octave=self.default_octave, **dc.asdict(note))
            else:
                prev = prev.closest(note)
            yield prev
