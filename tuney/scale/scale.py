from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from typing import Any, Protocol, runtime_checkable

from ..types import Frequency, NoteNumber


@runtime_checkable
class Tuning(Protocol):
    def __call__(self, note_number: NoteNumber) -> Frequency: ...


@runtime_checkable
class ToName(Protocol):
    def __call__(self, note_number: NoteNumber, **kwargs: Any) -> str: ...


@runtime_checkable
class ToNumber(Protocol):
    def __call__(self, name: str) -> NoteNumber: ...


@runtime_checkable
class Scale(Protocol):
    tuning: Tuning
    to_name: ToName
    to_number: ToNumber


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
