from __future__ import annotations

import re
import string
from collections.abc import Iterable, Iterator
from contextlib import suppress
from enum import StrEnum, auto
from functools import cached_property
from itertools import batched, chain
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

from ..types import NoteNumber
from .tuning import TuningImpl

FLAT, SHARP = '♭', '♯'
HALF_FLAT, HALF_SHARP = 'v', '^'
CANONICAL = {'b': FLAT, '#': SHARP}
ACCIDENTALS = FLAT + SHARP + HALF_FLAT + HALF_SHARP
ACCIDENTAL_CANONICAL = {
    '#': SHARP,
    'b': FLAT,
    FLAT: FLAT,
    SHARP: SHARP,
    HALF_FLAT: HALF_FLAT,
    HALF_SHARP: HALF_SHARP,
}
INTERVALS = [int(i) for i in '2212221']


def canonical(s: str) -> str:
    for k, v in CANONICAL.items():
        s = s.replace(k, v)
    return s


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


class Accidentals(StrEnum):
    none = auto()
    whole = auto()
    half = auto()


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
    alphabet: str = string.ascii_uppercase

    #: The root note to start scales with
    root: str = 'C'

    #: The first note from the alphabet:
    # TODO: validate begin <= base <= end
    begin: str = 'A'

    #: The Last note from the alphabet
    end: str = 'G'

    # If `notes` is set, once the scale is generated, only the notes in
    # `notes` are actually used in the list.
    #
    # For example, notes='CDEFGAB' would correspond to only
    # the white notes on the piano.
    notes: str | None = None

    # The intervals between notes. Can also be entered as a string: "2212221"
    intervals: Annotated[list[int], validate_intervals] = Field(
        default_factory=lambda: list(INTERVALS)
    )

    # Which accidentals are allowed in note names
    accidentals: Accidentals = Accidentals.whole

    #: Offset all note numbers by this
    offset: int = 0

    #: The Tuning for this Scale
    tuning: TuningImpl = TuningImpl()

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
        if not self._accidentals:
            return re.compile(rf'([{self.names}])')
        return re.compile(rf'([{self.names}][{re.escape(self._accidentals)}]*)')

    def _to_notes(self, s: str) -> tuple[list[str], list[str]]:
        split = self._note_re.split(canonical(s)) + ['']
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
                    flat = self._accidental_name(next_note, interval - j, False)
                    sharp = self._accidental_name(note, j, True)
                    if self.accidentals == Accidentals.half and j > interval // 2:
                        flats.append(sharp)
                        sharps.append(flat)
                    else:
                        flats.append(flat)
                        sharps.append(sharp)

        return tuple(flats), tuple(sharps)

    @cached_property
    def _accidentals(self) -> str:
        return {
            Accidentals.none: '',
            Accidentals.whole: FLAT + SHARP,
            Accidentals.half: ACCIDENTALS,
        }[self.accidentals]

    def _accidental_name(self, note: str, offset: int, use_sharp: bool) -> str:
        match self.accidentals:
            case Accidentals.none:
                return note
            case Accidentals.whole:
                accidental = SHARP if use_sharp else FLAT
                return note + accidental * offset
            case Accidentals.half:
                large = SHARP if use_sharp else FLAT
                small = HALF_SHARP if use_sharp else HALF_FLAT
                return note + large * (offset // 2) + small * (offset % 2)

    def _split_note_octave(self, s: str) -> tuple[str, str]:
        if s and s[0] in self.names:
            note = s[0]
            s = s[1:]
            while (
                s
                and (accidental := ACCIDENTAL_CANONICAL.get(s[0]))
                and accidental in self._accidentals
            ):
                note += accidental
                s = s[1:]
            return note, s
        raise ValueError(f'Bad number {s=}')
