from __future__ import annotations

import string
from typing import Annotated

from pydantic import Field
from reccy.configuration.tyro import tyro_option
from ufor import scale
from ufor.accidentals import Accidentals
from ufor.scale import validate_intervals

from ..config.annotations import Beginner, Display, Numeric


class Scale(scale.Scale, frozen=False):
    """A generalized musical Scale, where the default is "regular tuning".

    The common Western scale has
    * 12 equal-tempered semitones per octave
    * Note names CDEFGAB, with intervals of 2212221 semitones between them
    * FLAT to lower pitch by a semitone, SHARP to raise it

    Scale generalizes this to allow more or less than 12 notes per octave, N-just limit,
    custom tunings, different note names and intervals.
    """

    #: The base note names
    note_names: Annotated[str, tyro_option('-A'), Display(row=2)] = (
        string.ascii_uppercase
    )

    #: The root note to start scales with
    root: Annotated[str, tyro_option('-q'), Beginner, Numeric(row=0, width=1)] = 'C'

    #: The first note from the note names:
    # TODO: validate begin <= base <= end
    begin: Annotated[str, tyro_option('-j'), Numeric(column=1, row=0, width=1)] = 'A'

    #: The Last note from the alphabet
    end: Annotated[str, tyro_option('-E'), Numeric(column=2, row=0, width=1)] = 'G'

    # If `notes` is set, once the scale is generated, only the notes in
    # `notes` are actually used in the list.
    #
    # For example, notes='CDEFGAB' would correspond to only
    # the white notes on the piano.
    notes: Annotated[
        str | None, tyro_option('-Q'), Beginner, Numeric(row=1, width=12)
    ] = None

    # The intervals between notes. Can also be entered as a string: "2212221"
    intervals: Annotated[
        list[int],
        validate_intervals,
        tyro_option('-i'),
        Display(column=1, row=1, width=7),
    ] = Field(default_factory=lambda: list(scale.INTERVALS))

    # Which accidentals are allowed in note names
    accidentals: Annotated[Accidentals, tyro_option('-X'), Display(column=2, row=1)] = (
        Accidentals.whole
    )

    #: Offset all note numbers by this
    offset: Annotated[
        int,
        tyro_option('-Y', name='scale-offset'),
        Numeric(column=3, row=0, min=-99, max=99, width=3),
    ] = Field(0, ge=-99, le=99)
