from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from typing import Any, Protocol, runtime_checkable

type Frequency = float  # Must be non-negative
type NoteNumber = int  # May be negative


@runtime_checkable
class Tuning(Protocol):
    def __call__(self, note_number: NoteNumber) -> Frequency: ...


@runtime_checkable
class ToNumber(Protocol):
    def __call__(self, name: str) -> NoteNumber: ...


@runtime_checkable
class ToName(Protocol):
    def __call__(self, note_number: NoteNumber, **kwargs: Any) -> str: ...


@runtime_checkable
class ScaleP(Protocol):
    tuning: Tuning
    to_number: ToNumber
    to_name: ToName


@dc.dataclass
class Scale(ScaleP):
    tuning: Tuning
    to_number: ToNumber
    to_name: ToName


@dc.dataclass(frozen=True)
class Note:
    scale: Scale
    number: NoteNumber
    name: str

    @cached_property
    def frequency(self) -> float:
        return self.scale.tuning(self.number)

    @staticmethod
    def make(scale: Scale, n: NoteNumber | str) -> Note:
        if isinstance(n, str):
            name, number = n, scale.to_number(n)
        else:
            name, number = scale.to_name(n), n
        return Note(scale, number, name)
