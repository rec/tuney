from __future__ import annotations

from enum import StrEnum, auto
from fractions import Fraction
from functools import cached_property
from typing import Annotated

from pydantic import BaseModel, Field

from ..config.display import Beginner, Display, Numeric
from ..config.tyro_option import tyro_option
from . import NoteNumber, Number, cents
from .ratios import Ratios
from .table import Table


class Type(StrEnum):
    computed = auto()
    table = auto()
    ratios = auto()


class Computed(BaseModel):
    #: If limit is greater than zero, use rounded N-limit just intonation
    limit: Annotated[
        int, tyro_option('-v'), Display(column=1, row=0), Numeric(min=0, width=3)
    ] = Field(0, ge=0)

    #: Number of divisions of an octave
    notes_per_octave: Annotated[
        int,
        tyro_option('-V'),
        Beginner,
        Display(column=2, row=0),
        Numeric(min=1, width=3),
    ] = Field(12, gt=0)

    #: Frequency change between octaves. For the default "power" pitch_to_frequency
    #: the change is a ratio, so if it's 2, each octave is twice the frequency of the
    #: last; for "linear", it's a difference, so if it's 100, each octave would be
    #: 100Hz greater in frequency than the previous.
    octave_ratio: Annotated[
        float,
        tyro_option('-J'),
        Display(column=3, row=0),
        Numeric(min=0.001, inc=0.001),
    ] = Field(2, gt=0)

    def __call__(self, note_delta: NoteNumber) -> Number:
        r = self.octave_ratio ** (note_delta / self.notes_per_octave)
        return Fraction(r).limit_denominator(self.limit) if self.limit else r

    def as_ratios(self) -> Ratios:
        return Ratios.from_strings(
            str(self(i + 1)) for i in range(self.notes_per_octave)
        )


class Tuning(BaseModel, arbitrary_types_allowed=True):
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12-tet) but
    can be customized.
    """

    #: Which tuning source to use
    type: Annotated[Type | None, tyro_option(), Display(column=0, row=0)] = (
        Type.computed
    )

    #: Computed tuning parameters
    computed: Annotated[Computed | None, Beginner] = Field(default_factory=Computed)

    #: Absolute frequencies, indexed by note number
    table: Annotated[Table | None, tyro_option(), Display(row=1, width=24)] = None

    #: Ratio expressions, relative to root_frequency
    ratios: Annotated[Ratios | None, tyro_option(), Display(row=1, width=24)] = None

    #: Detune everything, in cents of an octave division
    detune: Annotated[
        float,
        tyro_option('-T'),
        Beginner,
        Display(column=1, row=0),
        Numeric(decimals=0, inc=1),
    ] = 0

    #: The frequency of the reference `root_note`
    root_frequency: Annotated[
        float,
        tyro_option('-U'),
        Beginner,
        Display(column=4, row=0),
        Numeric(min=0.001),
    ] = Field(440, gt=0)

    #: The note number of the reference note
    root_note: Annotated[
        NoteNumber,
        tyro_option('-W'),
        Display(column=5, row=0),
        Numeric(min=0, max=127, width=3),
    ] = 69  # MIDI note 69 is A440, for non-Yamaha units

    @cached_property
    def detune_ratio(self) -> float:
        return cents(self.detune)

    @property
    def active(self) -> Computed | Ratios | Table:
        default = getattr(self, self.type.name if self.type else '')
        if p := default or self.table or self.ratios or self.computed:
            return p
        return Computed()

    def __call__(self, note_number: NoteNumber) -> Number:
        """Return the frequency in this tuning for a NoteNumber"""
        note_delta = note_number - self.root_note
        tuning = self.active
        freq = tuning(note_delta)
        if not isinstance(tuning, Table):
            freq *= self.root_frequency
        return freq * self.detune_ratio
