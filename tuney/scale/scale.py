from __future__ import annotations

from typing import Callable, NamedTuple

type Frequency = float  # Must be non-negative
type NoteNumber = int  # May be negative
type NumberToFrequency = Callable[[NoteNumber], Frequency]
type Tuning = NumberToFrequency

type NameToNumber = Callable[[str], NoteNumber]
type NumberToName = Callable[[NoteNumber, ...], str]


class Scale(NamedTuple):
    tuning: Tuning
    name_to_number: NameToNumber
    number_to_name: NumberToName


class XNote(NamedTuple):  # The future of Note
    scale: Scale
    number: NoteNumber
    name: str

    @staticmethod
    def make(scale: Scale, n: NoteNumber | str) -> XNote:
        if isinstance(n, str):
            name, number = n, scale.name_to_number(n)
        else:
            name, number = scale.number_to_name(n), n  # ty: ignore[missing-argument]
        return XNote(scale, number, name)
