from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from ..types import NoteNumber
from .scale import Scale


@dc.dataclass(frozen=True)
class Note:
    scale: Scale
    name: str
    number: NoteNumber

    @cached_property
    def frequency(self) -> float:
        return self.scale.tuning(self.number)

    @staticmethod
    def make(scale: Scale, n: NoteNumber | str) -> Note:
        if isinstance(n, str):
            name, number = n, scale.to_number(n)
        else:
            name, number = scale.to_name(n), n
        return Note(scale=scale, name=name, number=number)
