from __future__ import annotations

from typing import Callable, NamedTuple

type Frequency = float  # Must be non-negative
type NoteNumber = int  # May be negative
type NumberToFrequency = Callable[[NoteNumber], Frequency]
type Scale = NumberToFrequency

type NameToNumber = Callable[[str], NoteNumber]
type NumberToName = Callable[[NoteNumber, ...], str]


class NamedScale(NamedTuple):
    scale: Scale
    name_to_number: NameToNumber
    number_to_name: NumberToName


class NoteFrequency(NamedTuple):
    number: NoteNumber
    frequency: Frequency
