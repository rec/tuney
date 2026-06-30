from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Protocol, runtime_checkable

import tyro
from pydantic import BaseModel, Field

from ..named_enum import NamedEnum
from ..types import Frequency, NoteNumber

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


class PitchToFrequencyFunction(NamedEnum):
    power = (power,)
    linear = (linear,)


class PitchToFrequency(BaseModel, frozen=True):
    #: The base rule for converting a pitch to a frequency
    function: Annotated[
        PitchToFrequencyFunction,
        tyro.conf.arg(name='pitch-function', aliases=['-F'], prefix_name=False),
    ] = PitchToFrequencyFunction.power

    def __call__(self, root: Frequency, change: float, octaves: float) -> float:
        return self.function.value[0](root, change, octaves)


class Tuning(BaseModel, frozen=True, arbitrary_types_allowed=True):
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12-tet) but
    can be customized.
    """

    #: Detune everything, in cents of an octave division
    detune: Annotated[float, tyro.conf.arg(aliases=['-T'], prefix_name=False)] = 0

    #: If limit is greater than zero, use rounded N-limit just intonation
    limit: Annotated[int, tyro.conf.arg(aliases=['-v'], prefix_name=False)] = 0

    #: Number of divisions of an octave
    notes_per_octave: Annotated[
        int, tyro.conf.arg(aliases=['-V'], prefix_name=False)
    ] = 12

    #: Frequency change between octaves. For the default "power" pitch_to_frequency
    #: the change is a ratio, so if it's 2, each octave is twice the frequency of the
    #: last; for "linear", it's a difference, so if it's 100, each octave would be
    #: 100Hz greater in frequency than the previous.
    octave_ratio: Annotated[float, tyro.conf.arg(aliases=['-J'], prefix_name=False)] = 2

    #: The rule for converting a pitch to a frequency
    pitch_to_frequency: PitchToFrequency = PitchToFrequency()

    #: The frequency of the reference `root_note`
    root_frequency: Annotated[
        Frequency, tyro.conf.arg(aliases=['-U'], prefix_name=False)
    ] = 440

    #: The note number of the reference note
    root_note: Annotated[
        NoteNumber, tyro.conf.arg(aliases=['-W'], prefix_name=False)
    ] = 69  # MIDI note 69 is A440, for non-Yamaha units

    #: A table, either a Sequence or a dict, mapping note number to frequency.
    table: Annotated[
        list[Frequency] | dict[NoteNumber, Frequency],
        tyro.conf.arg(prefix_name=False),
    ] = Field(default_factory=list)

    #: If table_blend is True, then notes that aren't found in the table are then
    #: looked up with the default algorithm.
    table_blend: Annotated[bool, tyro.conf.arg(prefix_name=False)] = True

    def __call__(self, note_number: NoteNumber) -> float:
        """Return the frequency in this tuning for a NoteNumber"""
        if isinstance(self.table, dict) or note_number >= 0:
            try:
                return self.table[note_number]
            except (KeyError, IndexError):
                if not self.table_blend:
                    raise

        divisions = note_number - self.root_note + self.detune / 100.0
        octaves = divisions / self.notes_per_octave

        f = self.pitch_to_frequency(self.root_frequency, self.octave_ratio, octaves)
        if self.limit:
            return float(Fraction(f).limit_denominator(self.limit))
        return f


assert isinstance(Tuning(), TuningP)
