from __future__ import annotations

import dataclasses as dc
from collections.abc import Sequence
from contextlib import nullcontext, suppress
from typing import cast

from ..types import Fraction, Frequency, NoteNumber, Number
from .scale import Tuning

# TODO: make sure we can serialize and deserialize Fraction (as str)


@dc.dataclass(frozen=True)
class ToneTuning(Tuning):
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12tet) but
    can be customized.
    """

    #: If limit_denominator is greater than zero, use N-limit just intonation
    limit_denominator: int = 0

    #: Number of divisions of an octave
    octave_divisions: int = 12

    #: Frequency ratio between two octaves
    octave_ratio: Number = 2

    #: The frequency of the reference `root_note`
    root_frequency: Frequency = 440

    #: The note number of the reference note
    root_note: NoteNumber = 69  # MIDI note 69 is A440, for non-Yamaha units

    #: A table, either a Sequence or a dict, mapping note number to frequency.
    table: Sequence[Frequency] | dict[NoteNumber, Frequency] = ()

    #: If table_blend is True, then notes that aren't found in the table are then
    #: looked up with the default algorithm.
    table_blend: bool = True

    def __call__(self, note_number: NoteNumber) -> Frequency:
        with suppress(KeyError, IndexError) if self.table_blend else nullcontext():
            return self.table[note_number]

        octaves = (note_number - self.root_note) / self.octave_divisions
        freq = self.root_frequency * cast(float, self.octave_ratio**octaves)
        ld = self.limit_denominator
        return Fraction(cast(float, freq)).limit_denominator(ld) if ld > 0 else freq
