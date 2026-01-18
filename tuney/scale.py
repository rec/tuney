from __future__ import annotations


from abc import ABC, abstractmethod
from typing import Any, Sequence


type NoteNumber = int  # May be negative


class NoteNamer(ABC):
    @abstractmethod
    def to_number(self, name: str) -> int: ...

    @abstractmethod
    def to_name(self, number: NoteNumber, **kwargs: Any) -> str | None: ...


class Scale(ABC):
    namers: Sequence[NoteNamer]

    @abstractmethod
    def number_to_frequency(self, note_number: NoteNumber) -> float: ...

    def nearest_note_numbers(self, frequency: float) -> tuple[int, int]:
        below = above = 0
        f = self.number_to_frequency
        while f(below) > frequency:
            below = (2 * below) if below else -100
        while f(above) < frequency:
            above = (2 * above) if above else 100
        while (above - below) > 1:
            mid = (below + above) // 2
            assert below < mid < above, (below, mid, above)
            assert f(below) < f(mid) < f(above), (below, mid, above)
            if f(mid) < frequency:
                below = mid
            else:
                above = mid
        return below, above

    def to_name(self, note_number: NoteNumber, **kwargs: Any) -> str:
        for n in self.namers:
            if (s := n.to_name(note_number, **kwargs)) is not None:
                return s
        raise ValueError(f"Can't name {note_number=}, {kwargs=}")
