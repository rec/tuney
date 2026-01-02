from __future__ import annotations

from functools import cached_property
import dataclasses as dc
import re


ACCIDENTAL_DICT = {"#": "♯", "b": "♭", "♭": "♭", "♯": "♯"}
ACCIDENTALS = "".join(ACCIDENTAL_DICT)
CANONICALS = "♭♯"

NOTE_RE = re.compile(rf"([A-G])([{ACCIDENTALS}]*)(-?\d*)")

NOTES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

MIDI_ZERO_OCTAVE = -1
"""
0 would be Yamaha, but we'll account for that elsewhere.
Standard: 60 = C3, C-1 == 0
Yamaha: 60 = C4, C0 == 0
"""


def canonical(s: str) -> str:
    for k, v in ACCIDENTAL_DICT.items():
        s = s.replace(k, v)
    return s


@dc.dataclass(frozen=True)
class Note:
    name: str
    accidentals: str = ""

    @staticmethod
    def make(note_name: str) -> Note:
        if not (m := NOTE_RE.match(note_name)):
            raise ValueError(f"Cannot understand note {note_name}")

        name, accidentals, octave = m.groups()
        acc = canonical(accidentals)
        return NoteOctave(name, acc, int(octave)) if octave else Note(name, acc)

    def __post_init__(self):
        assert self.name in NOTES, self
        assert all(a in CANONICALS for a in self.accidentals), self

    def __repr__(self) -> str:
        return self.name + self.accidentals

    @cached_property
    def offset(self) -> int:
        """In semitones from C"""
        return NOTES[self.name] + sum(-1 + 2 * (a == "♯") for a in self.accidentals)


@dc.dataclass(frozen=True)
class NoteOctave(Note):
    octave: int = 0

    def __repr__(self) -> str:
        return f"{super().__repr__()}{self.octave}"

    def closest(self, n: Note) -> NoteOctave:
        """Octave version of n which is closest as possible to self"""
        if isinstance(n, NoteOctave):
            return n
        off = self.offset - n.offset
        delta = 1 if off <= -5 else 0 if off <= 5 else -1
        assert -11 <= off <= 11, (off, n, delta)
        return NoteOctave(octave=self.octave + delta, **dc.asdict(n))

    @cached_property
    def note_number(self) -> int:
        return 12 * (self.octave - MIDI_ZERO_OCTAVE) + self.offset
