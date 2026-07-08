from __future__ import annotations

from fractions import Fraction
from functools import cached_property
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ..display import Beginner, Display
from ..named_enum import NamedEnum
from ..tyro_option import tyro_option
from . import NoteNumber, cents
from .root import Root

type Frequency = float  # Must be non-negative

# TODO: make sure we can serialize and deserialize Fraction (as str)


@runtime_checkable
class TuningP(Protocol):
    def __call__(self, note_number: NoteNumber) -> Frequency: ...


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

    def __call__(self, note_number: NoteNumber, root: Root) -> float:
        divisions = note_number - root.note
        octaves = divisions / self.notes_per_octave

        f = self.pitch_to_frequency(root.frequency, self.octave_ratio, octaves)
        if self.limit:
            return float(Fraction(f).limit_denominator(self.limit))
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

    #: A table, either a Sequence or a dict, mapping note number to frequency.
    table: Annotated[
        list[Frequency] | dict[NoteNumber, Frequency],
        tyro_option(),
        Display(row=1),
    ] = Field(default_factory=list)

    #: If table_blend is True, then notes that aren't found in the table are then
    #: looked up with the default algorithm.
    table_blend: Annotated[bool, tyro_option(), Display(column=6, row=0)] = True

    @cached_property
    def detune_ratio(self) -> float:
        return cents(self.detune)

    def __call__(self, note_number: NoteNumber) -> float:
        """Return the frequency in this tuning for a NoteNumber"""
        if isinstance(self.table, dict) or note_number >= 0:
            try:
                return self.table[note_number] * self.detune_ratio
            except (KeyError, IndexError):
                if not self.table_blend:
                    raise

        return self.computed(note_number, self.root) * self.detune_ratio


assert isinstance(Tuning(), TuningP)
