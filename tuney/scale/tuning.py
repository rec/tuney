from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from functools import cached_property
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, model_validator

from ..display import Beginner, Display
from ..tyro_option import tyro_option
from . import NoteNumber, Number, cents
from .ratios import Ratios

type Frequency = float  # Must be non-negative


@runtime_checkable
class TuningP(Protocol):
    def __call__(self, note_number: NoteNumber) -> Number: ...


@runtime_checkable
class ToFrequency(Protocol):
    def __call__(
        self, root_frequency: float, octave_ratio: float, octaves: float
    ) -> Number: ...


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

    def __call__(self, note_delta: NoteNumber) -> Number:
        r = self.octave_ratio ** (note_delta / self.notes_per_octave)
        return Fraction(r).limit_denominator(self.limit) if self.limit else r

    def as_ratios(self) -> Ratios:
        return Ratios(ratios=[self(i + 1) for i in range(self.notes_per_octave)])


class Tuning(BaseModel, frozen=True, arbitrary_types_allowed=True):
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12-tet) but
    can be customized.
    """

    tuning: Computed | Ratios | list[Frequency] = Computed()

    #: Detune everything, in cents of an octave division
    detune: Annotated[float, tyro_option('-T'), Beginner, Display(row=0)] = 0

    #: The frequency of the reference `root_note`
    root_frequency: Annotated[
        float,
        tyro_option('-U'),
        Beginner,
        Display(column=4, row=0),
    ] = 440

    #: The note number of the reference note
    root_note: Annotated[
        NoteNumber,
        tyro_option('-W'),
        Beginner,
        Display(column=5, row=0),
    ] = 69  # MIDI note 69 is A440, for non-Yamaha units

    @model_validator(mode='before')
    @classmethod
    def _normalize_source(cls, data: object) -> object:
        return dict(data) if isinstance(data, Mapping) else data

    @cached_property
    def detune_ratio(self) -> float:
        return cents(self.detune)

    def __call__(self, note_number: NoteNumber) -> Number:
        """Return the frequency in this tuning for a NoteNumber"""
        note_delta = note_number - self.root_note
        if isinstance(self.tuning, list):
            freq = self.tuning[note_delta % len(self.tuning)]
        else:
            freq = self.tuning(note_delta) * self.root_frequency
        return freq * self.detune_ratio


assert isinstance(Tuning(), TuningP)
