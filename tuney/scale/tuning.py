from __future__ import annotations

from fractions import Fraction
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ..named_enum import NamedEnum
from ..types import Frequency, NoteNumber

# TODO: make sure we can serialize and deserialize Fraction (as str)


@runtime_checkable
class Tuning(Protocol):
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
    function: PitchToFrequencyFunction = PitchToFrequencyFunction.power

    def __call__(self, root: Frequency, change: float, octaves: float) -> float:
        return self.function.value[0](root, change, octaves)


class TuningImpl(BaseModel, frozen=True, arbitrary_types_allowed=True):
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12-tet) but
    can be customized.
    """

    #: Detune everything, in cents of an octave division
    detune: float = 0

    #: If limit is greater than zero, use rounded N-limit just intonation
    limit: int = 0

    #: Number of divisions of an octave
    notes_per_octave: int = 12

    #: Frequency change between octaves. For the default "power" pitch_to_frequency
    #: the change is a ratio, so if it's 2, each octave is twice the frequency of the
    #: last; for "linear", it's a difference, so if it's 100, each octave would be
    #: 100Hz greater in frequency than the previous.
    octave_ratio: float = 2

    #: The rule for converting a pitch to a frequency
    pitch_to_frequency: PitchToFrequency = PitchToFrequency()

    #: The frequency of the reference `root_note`
    root_frequency: Frequency = 440

    #: The note number of the reference note
    root_note: NoteNumber = 69  # MIDI note 69 is A440, for non-Yamaha units

    #: A table, either a Sequence or a dict, mapping note number to frequency.
    table: list[Frequency] | dict[NoteNumber, Frequency] = Field(default_factory=list)

    #: If table_blend is True, then notes that aren't found in the table are then
    #: looked up with the default algorithm.
    table_blend: bool = True

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


assert isinstance(TuningImpl(), Tuning)
