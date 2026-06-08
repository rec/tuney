from __future__ import annotations

import string
from collections.abc import Iterable, Iterator
from contextlib import suppress
from functools import cached_property
from itertools import chain
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import BaseModel, BeforeValidator, Field

from ..types import NoteNumber
from .tuning import Tuning, TuningImpl

FLAT, SHARP = '♭', '♯'
ACCIDENTALS = {'#': 1, 'b': -1, '♭': -1, '♯': 1}
INTERVALS = [int(i) for i in '2212221']


@BeforeValidator
def validate_intervals(it: str | Iterable[int | str]) -> list[int]:
    intervals, errors = [], []
    for c in it:
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
    * ♭ to lower pitch by a semitone, '♯' to raise it

    Scale generalizes this to allow more or less than 12 notes per octave, N-just limit,
    custom tunings, different note names and intervals

    """

    #: The base alphabet
    alphabet: str = string.ascii_uppercase

    #: The base note to start scales with
    base: str = 'C'

    #: The first note from the alphabet
    begin: str = 'A'

    #: The Last note from the alphabet
    end: str = 'G'

    # The intervals between notes. Can also be entered as a string: "2212221"
    intervals: Annotated[list[int], validate_intervals] = Field(
        default_factory=lambda: list(INTERVALS)
    )

    #: Offset all note numbers by this
    offset: int = 0

    #: The Tuning for this Scale
    tuning: TuningImpl = TuningImpl()

    # Implements Scale.to_name
    def to_name(self, note_number: NoteNumber, use_sharp: bool = True) -> str:
        octave, offset = divmod(note_number - self.offset, self.octave_length)
        name = self.flats_sharps[use_sharp][offset]
        return f'{name}{octave}'

    # Implements Scale.to_number
    def to_number(self, s: str) -> NoteNumber:
        if (n := self._note_to_semitones.get(s[0])) is not None:
            s = s[1:]
            while s and (a := ACCIDENTALS.get(s[0])):
                n += a
                s = s[1:]
            with suppress(ValueError):
                return n + self.offset + self.octave_length * int(s)

        raise ValueError(f'Bad number {s=}')

    @cached_property
    def names(self) -> str:
        a = self.alphabet
        begin, end, base = a.index(self.begin), a.index(self.end), a.index(self.base)
        return ''.join(a[i] for i in chain(range(base, end + 1), range(begin, base)))

    @cached_property
    def octave_length(self) -> int:
        return len(self.flats_sharps[0])

    def _note_interval_semitone(self) -> Iterator[tuple[str, int, int]]:
        assert self.intervals
        L = len(self.intervals)
        semitone = 0
        for i, note in enumerate(self.names):
            interval = self.intervals[i % L]
            yield note, interval, semitone
            semitone += interval

    @cached_property
    def flats_sharps(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        flats, sharps = [], []
        for i, (note, interval, _) in enumerate(self._note_interval_semitone()):
            flats.append(note)
            sharps.append(note)
            if interval > 1:
                next_note = self.names[(i + 1) % len(self.names)]
                for j in range(1, interval):
                    flats.append(next_note + FLAT * (interval - j))
                    sharps.append(note + SHARP * j)

        return tuple(flats), tuple(sharps)

    @cached_property
    def _note_to_semitones(self) -> dict[str, NoteNumber]:
        return {n: s for n, _, s in self._note_interval_semitone()}


# TODO: we don't really allow purely general Scales anymore, but it
# was the type system that killed us. Delete everything below this line?


@runtime_checkable
class ToName(Protocol):
    def __call__(self, note_number: NoteNumber, **kwargs: Any) -> str: ...


@runtime_checkable
class ToNumber(Protocol):
    def __call__(self, name: str) -> NoteNumber: ...


@runtime_checkable
class ScaleI(Protocol):
    tuning: Tuning
    to_name: ToName
    to_number: ToNumber


assert isinstance(Scale(), ScaleI)
