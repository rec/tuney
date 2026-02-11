from __future__ import annotations

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
