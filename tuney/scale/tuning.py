from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from functools import cached_property
from typing import Annotated, Protocol, Self, runtime_checkable

import tyro
from pydantic import BaseModel, Field, model_validator

from ..display import Beginner, Display
from ..named_enum import NamedEnum
from ..tyro_option import tyro_option
from . import NoteNumber, cents
from .ratios import Ratios
from .root import Root

type Frequency = float  # Must be non-negative

# TODO: make sure we can serialize and deserialize Fraction (as str)


@runtime_checkable
class TuningP(Protocol):
    def __call__(self, note_number: NoteNumber) -> Frequency | Fraction: ...


@runtime_checkable
class ToFrequency(Protocol):
    def __call__(
        self, root_frequency: float, octave_ratio: float, octaves: float
    ) -> Frequency: ...


def power(root: Frequency, change: float, octaves: float) -> float:
    return root * change**octaves


def linear(root: Frequency, change: float, octaves: float) -> float:
    return root + change * octaves


class PitchToFrequency(NamedEnum):
    power = (power,)
    linear = (linear,)

    def __call__(self, root: Frequency, change: float, octaves: float) -> float:
        return self.value[0](root, change, octaves)


class Computed(BaseModel, frozen=True):
    #: If limit is greater than zero, use rounded N-limit just intonation
    limit: Annotated[int, tyro_option('-v'), Display(column=1, row=0)] = 0

    #: Number of divisions of an octave
    notes_per_octave: Annotated[
        int, tyro_option('-V'), Beginner, Display(column=2, row=0)
    ] = 12

    #: Frequency change between octaves. For the default "power" pitch_to_frequency
    #: the change is a ratio, so if it's 2, each octave is twice the frequency of the
    #: last; for "linear", it's a difference, so if it's 100, each octave would be
    #: 100Hz greater in frequency than the previous.
    octave_ratio: Annotated[
        float, tyro_option('-J'), Beginner, Display(column=3, row=0)
    ] = 2

    #: The rule for converting a pitch to a frequency
    pitch_to_frequency: Annotated[PitchToFrequency, tyro_option('-F')] = (
        PitchToFrequency.power
    )

    def __call__(self, note_number: NoteNumber, root: Root) -> float | Fraction:
        divisions = note_number - root.note
        octaves = divisions / self.notes_per_octave

        f = self.pitch_to_frequency(root.frequency, self.octave_ratio, octaves)
        if self.limit:
            return Fraction(f).limit_denominator(self.limit)
        return f


class Tuning(BaseModel, frozen=True, arbitrary_types_allowed=True):
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12-tet) but
    can be customized.
    """

    #: Detune everything, in cents of an octave division
    detune: Annotated[float, tyro_option('-T'), Beginner, Display(row=0)] = 0

    root: Root = Root()
    computed: Computed = Computed()
    ratios: Annotated[
        tyro.conf.Suppress[Ratios],
        Display(),
    ] = Field(default_factory=Ratios, exclude_if=lambda ratios: not ratios.ratios)

    #: A table, either a Sequence or a dict, mapping note number to frequency.
    table: Annotated[
        list[Frequency] | None,
        tyro_option(),
        Display(row=1),
    ] = None

    #: If table_blend is True, then notes that aren't found in the table are then
    #: looked up with the default algorithm.
    table_blend: Annotated[bool, tyro_option(), Display(column=6, row=0)] = True

    @model_validator(mode='before')
    @classmethod
    def _normalize_source(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        values = dict(data)
        if values.get('table') == []:
            values['table'] = None
        return values

    @model_validator(mode='after')
    def _validate_source(self) -> Self:
        if self.table is not None and self.ratios.ratios:
            raise ValueError('only one explicit tuning source is allowed')
        return self

    @cached_property
    def detune_ratio(self) -> float:
        return cents(self.detune)

    def __call__(self, note_number: NoteNumber) -> float | Fraction:
        """Return the frequency in this tuning for a NoteNumber"""
        r = None
        if self.table is not None:
            r = self.table[note_number]
        elif self.ratios.ratios:
            r = self.ratios(note_number, self.root)
        else:
            r = self.computed(note_number, self.root)
        return r * self.detune_ratio


assert isinstance(Tuning(), TuningP)
