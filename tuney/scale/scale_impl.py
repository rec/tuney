from __future__ import annotations

import dataclasses as dc
import string
from contextlib import suppress
from functools import cached_property
from itertools import chain

from ..types import NoteNumber
from .scale import Scale, Tuning
from .tuning_impl import TuningImpl

MIDI_ZERO_OCTAVE = -1
FLAT, SHARP = '♭', '♯'
CANONICAL_DICT = {'#': '♯', 'b': '♭', '♭': '♭', '♯': '♯'}
ACCIDENTALS = {'#': 1, 'b': -1, '♭': -1, '♯': 1}


@dc.dataclass(frozen=True)
class ScaleImpl:
    #: The base alphabet - if not specified, use A-Z
    alphabet: str | None = None

    #: The base note to start scales with
    base: str = 'C'

    #: The first note from the alphabet
    begin: str = 'A'

    #: The Last note from the alphabet
    end: str = 'G'

    #: The list of notes which do not have a sharp: where the interval
    #: between the note and the next one is just a semitone
    no_sharp: str = 'BEILPSWZ'

    #: Offset all note numbers by this
    offset: int = 0

    #: The Tuning for this Scale
    tuning: Tuning = TuningImpl()

    # Implements Scale.to_name
    def to_name(self, note_number: NoteNumber, use_sharp: bool = True) -> str:
        octave, offset = divmod(note_number - self.offset, self.octave_length)
        name = self.number_to_name[use_sharp][offset]
        return f'{name}{octave}'

    # Implements Scale.to_number
    def to_number(self, s: str) -> NoteNumber:
        if (n := self.name_to_number.get(s[0])) is not None:
            s = s[1:]
            while s and (a := ACCIDENTALS.get(s[0])):
                n += a
                s = s[1:]
            with suppress(ValueError):
                return n + self.offset + self.octave_length * int(s)

        raise ValueError(f'Bad number {s=}')

    @cached_property
    def alphabet_(self) -> str:
        return string.ascii_uppercase if self.alphabet is None else self.alphabet

    @cached_property
    def name_to_number(self) -> dict[str, NoteNumber]:
        return self._nnt[0]

    @cached_property
    def names(self) -> str:
        a = self.alphabet_
        begin, end, base = a.index(self.begin), a.index(self.end), a.index(self.base)
        return ''.join(a[i] for i in chain(range(base, end + 1), range(begin, base)))

    @cached_property
    def number_to_name(self) -> dict[bool, list[str]]:
        return self._nnt[1]

    @cached_property
    def octave_length(self) -> int:
        return len(self.number_to_name[False])

    @cached_property
    def _nnt(self) -> tuple[dict[str, NoteNumber], dict[bool, list[str]]]:
        nn = {}
        sharp, flat = [], []
        semitones = 0
        for i, name in enumerate(self.names):
            nn[name] = semitones
            sharp.append(name)
            flat.append(name)

            if name in self.no_sharp:
                semitones += 1
            else:
                semitones += 2
                next_name = self.names[(i + 1) % len(self.names)]
                sharp.append(name + SHARP)
                flat.append(next_name + FLAT)

        return nn, {True: sharp, False: flat}


assert isinstance(ScaleImpl(), Scale)


if __name__ == '__main__':
    s = ScaleImpl()
    print(s.names)
    print(s.name_to_number)
