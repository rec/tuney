from __future__ import annotations

import re
import string
from collections.abc import Iterable, Iterator
from contextlib import suppress
from functools import cached_property
from itertools import batched, chain
from typing import Annotated

import tyro
from pydantic import BaseModel, BeforeValidator, Field

from ..types import NoteNumber
from .accidentals import AccidentalNames, Accidentals
from .tuning import Tuning

INTERVALS = [int(i) for i in '2212221']


@BeforeValidator
def validate_intervals(it: str | Iterable[int | str]) -> list[int]:
    intervals, errors = [], []
    for c in it:
        if isinstance(c, str) and c.isspace():
            continue
        try:
            i = int(c)
        except ValueError:
            errors.append(f'{c=} is not a number')
        else:
            if i < 0:
                errors.append(f'{c=} is less than 0')
            else:
                intervals.append(i)
    if not intervals:
        errors.append('No valid intervals')
    if errors:
        raise ValueError(*errors)
    return intervals


class Scale(BaseModel, frozen=True):
    """A generalized musical Scale, where the default is "regular tuning".

    The common Western scale has
    * 12 equal-tempered semitones per octave
    * Note names CDEFGAB, with intervals of 2212221 semitones between them
    * FLAT to lower pitch by a semitone, SHARP to raise it

    Scale generalizes this to allow more or less than 12 notes per octave, N-just limit,
    custom tunings, different note names and intervals.
    """

    #: The base alphabet
    alphabet: Annotated[
        str, tyro.conf.arg(name='scale-alphabet', aliases=['-A'], prefix_name=False)
    ] = string.ascii_uppercase

    #: The root note to start scales with
    root: Annotated[str, tyro.conf.arg(aliases=['-q'], prefix_name=False)] = 'C'

    #: The first note from the alphabet:
    # TODO: validate begin <= base <= end
    begin: Annotated[str, tyro.conf.arg(aliases=['-j'], prefix_name=False)] = 'A'

    #: The Last note from the alphabet
    end: Annotated[str, tyro.conf.arg(aliases=['-E'], prefix_name=False)] = 'G'

    # If `notes` is set, once the scale is generated, only the notes in
    # `notes` are actually used in the list.
    #
    # For example, notes='CDEFGAB' would correspond to only
    # the white notes on the piano.
    notes: Annotated[str | None, tyro.conf.arg(aliases=['-Q'], prefix_name=False)] = (
        None
    )

    # The intervals between notes. Can also be entered as a string: "2212221"
    intervals: Annotated[
        list[int], validate_intervals, tyro.conf.arg(aliases=['-i'], prefix_name=False)
    ] = Field(default_factory=lambda: list(INTERVALS))

    # Which accidentals are allowed in note names
    accidentals: Annotated[
        Accidentals, tyro.conf.arg(aliases=['-X'], prefix_name=False)
    ] = Accidentals.whole

    #: Offset all note numbers by this
    offset: Annotated[
        int, tyro.conf.arg(name='scale-offset', aliases=['-Y'], prefix_name=False)
    ] = 0

    #: The Tuning for this Scale
    tuning: Tuning = Tuning()

    # Implements Scale.to_name
    def to_name(self, note_number: NoteNumber, use_sharp: bool = True) -> str:
        octave, offset = divmod(note_number - self.offset, self.note_count)
        name = self.flats_sharps[use_sharp][offset]
        return f'{name}{octave}'

    # Implements Scale.to_number
    # This is only used in tests!
    def to_number(self, s: str) -> NoteNumber:
        note, octave_text = self._split_note_octave(s)
        if (semitones := self._note_to_semitones.get(note)) is not None:
            with suppress(ValueError):
                note_number = self.note_numbers.index(semitones)
                return note_number + self.offset + self.note_count * int(octave_text)

        raise ValueError(f'Bad number {s=}')

    def frequency(self, note_number: NoteNumber) -> float:
        return self.tuning(self.tuning_number(note_number))

    @cached_property
    def names(self) -> str:
        a = self.alphabet
        begin, root, end = a.index(self.begin), a.index(self.root), a.index(self.end)
        assert begin <= root <= end
        return ''.join(a[i] for i in chain(range(root, end + 1), range(begin, root)))

    @cached_property
    def octave_length(self) -> int:
        return sum(self.intervals)

    @cached_property
    def note_count(self) -> int:
        return len(self.flats_sharps[0])

    def tuning_number(self, note_number: NoteNumber) -> NoteNumber:
        octave, offset = divmod(note_number - self.offset, self.note_count)
        return self.note_numbers[offset] + self.octave_length * octave + self.offset

    def _note_interval_number(self) -> Iterator[tuple[str, int, int]]:
        assert self.intervals
        L = len(self.intervals)
        semitone = 0
        for i, note in enumerate(self.names):
            interval = self.intervals[i % L]
            yield note, interval, semitone
            semitone += interval

    @cached_property
    def _note_re(self) -> re.Pattern:
        if not self.accidental_names.symbols:
            return re.compile(rf'([{self.names}])')
        return re.compile(
            rf'([{self.names}][{re.escape(self.accidental_names.symbols)}]*)'
        )

    def _to_notes(self, s: str) -> tuple[list[str], list[str]]:
        split = self._note_re.split(self.accidental_names.canonical(s)) + ['']
        errors, values = zip(*batched(split, 2), strict=True)
        notes = [v for v in values[:-1] if v]
        if not notes:
            notes = list(self.names)
        return notes, [v for e in errors[:-1] if (v := e.strip())]

    @cached_property
    def flats_sharps(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return (
            tuple(
                note
                for i, note in enumerate(self.all_flats_sharps[0])
                if i in self.note_numbers
            ),
            tuple(
                note
                for i, note in enumerate(self.all_flats_sharps[1])
                if i in self.note_numbers
            ),
        )

    @cached_property
    def _note_to_semitones(self) -> dict[str, NoteNumber]:
        result = {}
        for n, notes in enumerate(zip(*self.all_flats_sharps, strict=True)):
            for note in notes:
                result.setdefault(note, n)
        return result

    @cached_property
    def note_numbers(self) -> tuple[NoteNumber, ...]:
        if self.notes is None:
            return tuple(range(self.octave_length))
        allowed_notes, _ = self._to_notes(self.notes)
        it = enumerate(zip(*self.all_flats_sharps, strict=True))
        return tuple(i for i, notes in it if set(notes).intersection(allowed_notes))

    @cached_property
    def all_flats_sharps(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        flats, sharps = [], []
        for i, (note, interval, _) in enumerate(self._note_interval_number()):
            flats.append(note)
            sharps.append(note)
            if interval > 1:
                next_note = self.names[(i + 1) % len(self.names)]
                for j in range(1, interval):
                    flat, sharp = self.accidental_names.flat_sharp_names(
                        note, next_note, interval, j
                    )
                    flats.append(flat)
                    sharps.append(sharp)

        return tuple(flats), tuple(sharps)

    @cached_property
    def accidental_names(self) -> AccidentalNames:
        return AccidentalNames(self.accidentals)

    def _split_note_octave(self, s: str) -> tuple[str, str]:
        return self.accidental_names.split_note(s, self.names)
