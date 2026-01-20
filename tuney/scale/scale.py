from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from . import NoteNumber


class Scale(ABC):
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


class NoteNamer(ABC):
    scale: Scale

    @abstractmethod
    def to_number(self, name: str) -> int: ...

    @abstractmethod
    def to_name(self, number: NoteNumber, **kwargs: Any) -> str: ...
