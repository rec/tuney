from __future__ import annotations

from functools import cached_property

from pydantic import BaseModel

from ..types import NoteNumber, Number
from .scale import Scale


class Note(BaseModel, frozen=True):
    scale: Scale
    name: str
    number: NoteNumber

    @cached_property
    def frequency(self) -> Number:
        return self.scale.tuning(self.number)

    @staticmethod
    def make(scale: Scale, n: NoteNumber | str) -> Note:
        if isinstance(n, str):
            name, number = n, scale.to_number(n)
        else:
            name, number = scale.to_name(n), n
        return Note(scale=scale, name=name, number=number)
