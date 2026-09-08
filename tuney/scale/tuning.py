from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated

from pydantic import BaseModel, Field
from reccy.configuration.tyro import tyro_option, unit_spec
from reccy.configuration.units import Hertz, MusicalCents
from ufor import tuning
from ufor.number import NoteNumber, Number

from ..config.annotations import Beginner, Display, Numeric
from .ratios import Ratios
from .table import Table


class Type(StrEnum):
    computed = auto()
    table = auto()
    ratios = auto()


class Computed(BaseModel):
    #: Maximum rational denominator; zero disables approximation
    limit: Annotated[
        int, tyro_option('-v'), Numeric(column=1, row=0, min=0, width=3)
    ] = Field(0, ge=0)

    #: Number of divisions of an octave
    notes_per_octave: Annotated[
        int,
        tyro_option('-V'),
        Beginner,
        Numeric(column=2, row=0, min=1, width=3),
    ] = Field(12, gt=0)

    #: Frequency change between octaves. For the default "power" pitch_to_frequency
    #: the change is a ratio, so if it's 2, each octave is twice the frequency of the
    #: last; for "linear", it's a difference, so if it's 100, each octave would be
    #: 100Hz greater in frequency than the previous.
    octave_ratio: Annotated[
        float,
        tyro_option('-J'),
        Numeric(column=3, row=0, min=0.001, inc=0.001),
    ] = Field(2, gt=0)

    @property
    def definition(self) -> tuning.Computed:
        return tuning.Computed(
            limit=self.limit,
            notes_per_octave=self.notes_per_octave,
            octave_ratio=str(self.octave_ratio),
        )

    def __call__(self, note_delta: NoteNumber) -> Number:
        return self.definition(note_delta)

    def as_ratios(self) -> Ratios:
        definition = self.definition.as_ratios()
        assert definition.repeat_ratio is not None
        return Ratios.from_strings([*definition.values[1:], definition.repeat_ratio])


class Tuning(BaseModel, arbitrary_types_allowed=True):
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12-tet) but
    can be customized.
    """

    #: Which tuning source to use
    type: Annotated[Type | None, Display(column=0, row=0)] = Type.computed

    #: Computed tuning parameters
    computed: Annotated[Computed | None, Beginner] = Field(default_factory=Computed)

    #: Absolute frequencies, indexed by note number
    table: Annotated[Table | None, Display(row=1, width=24)] = None

    #: Ratio expressions, relative to root_frequency
    ratios: Annotated[Ratios | None, Display(row=1, width=24)] = None

    #: Detune everything, in cents of an octave division
    detune: Annotated[
        MusicalCents,
        unit_spec(MusicalCents, 'CENTS'),
        tyro_option('-T'),
        Beginner,
        Numeric(column=1, row=0, decimals=0, inc=1),
    ] = 0

    #: The frequency of the reference `root_note`
    root_frequency: Annotated[
        Hertz,
        unit_spec(Hertz, 'HERTZ'),
        tyro_option('-U'),
        Beginner,
        Numeric(column=4, row=0, min=0.001),
    ] = Field(440, gt=0)

    #: The note number of the reference note
    root_note: Annotated[
        NoteNumber,
        tyro_option('-W'),
        Numeric(column=5, row=0, min=0, max=127, width=3),
    ] = Field(69, ge=0, le=127)  # MIDI note 69 is A440, for non-Yamaha units

    @property
    def active(self) -> Computed | Ratios | Table:
        default = getattr(self, self.type.name) if self.type else None
        if p := default or self.table or self.ratios or self.computed:
            return p
        return Computed()

    @property
    def definition(self) -> tuning.Tuning:
        source = self.active.definition
        if isinstance(source, tuning.FrequencyTable):
            source = source.model_copy(update={'first_note': self.root_note})
        return tuning.Tuning(
            source=source,
            root_note=self.root_note,
            root_frequency=str(self.root_frequency),
            detune=self.detune,
        )

    def __call__(self, note_number: NoteNumber) -> Number:
        """Resolve pitch; wrapping a finite instrument range is Tuney policy."""
        if isinstance(active := self.active, Table):
            if not active.values:
                raise ValueError('No frequency table configured')
            note_number = self.root_note + (note_number - self.root_note) % len(
                active.values
            )
        return self.definition(note_number)
