from __future__ import annotations

import dataclasses as dc
from collections.abc import Sequence
from typing import cast

from ..types import Fraction, Frequency, NoteNumber, Number

# TODO: make sure we can serialize and deserialize Fraction (as str)


@dc.dataclass(frozen=True)
class Tuning:
    """
    A generalized Tuning, a function from NoteNumber to Frequency.
    """

    #: If this is positive, then use N limit just intonation
    limit_denominator: int = 0
    octave_divisions: int = 12
    octave_ratio: Number = 2
    root_frequency: Frequency = 440
    root_note: NoteNumber = 69  # MIDI note 69 is A440, for non-Yamaha units
    table: Sequence[Frequency] | dict[NoteNumber, Frequency] | None = None
    table_blend: bool = False

    def __call__(self, note_number: NoteNumber) -> Frequency:
        if self.table is not None:
            try:
                return self.table[note_number]
            except (KeyError, IndexError):
                if not self.table_blend:
                    raise

        octaves = (note_number - self.root_note) / self.octave_divisions
        freq = self.root_frequency * cast(float, self.octave_ratio**octaves)
        ld = self.limit_denominator
        return Fraction(cast(float, freq)).limit_denominator(ld) if ld > 0 else freq
