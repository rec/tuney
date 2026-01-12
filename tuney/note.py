from __future__ import annotations

from functools import cache, cached_property
import dataclasses as dc
import re


MIDI_ZERO_OCTAVE = -1
"""
0 would be Yamaha, but we'll account for that elsewhere.
Standard: 60 = C3, C-1 == 0
Yamaha: 60 = C4, C0 == 0
"""
A4 = 69

ACCIDENTAL_DICT = {"#": "♯", "b": "♭", "♭": "♭", "♯": "♯"}
ACCIDENTALS = "#b♭♯"
assert ACCIDENTALS == "".join(sorted(ACCIDENTAL_DICT))

FLAT, SHARP = "♭", "♯"
CANONICALS = FLAT + SHARP
assert CANONICALS == ACCIDENTALS[2:]

NOTE_TO_NUMBER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NUMBER_TO_NOTES = {
    FLAT: ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"),
    SHARP: ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"),
}

NOTE_RE = re.compile(rf"([A-G])([{ACCIDENTALS}]*)(-?\d*)")


def canonical(s: str) -> str:
    for k, v in ACCIDENTAL_DICT.items():
        s = s.replace(k, v)
    return s


@dc.dataclass(frozen=True)
class NoteName:
    """A note without an octave"""

    name: str
    accidentals: str = ""

    def __post_init__(self):
        assert self.name in NOTE_TO_NUMBER, self
        assert all(a in CANONICALS for a in self.accidentals), self

    def __repr__(self) -> str:
        return self.name + self.accidentals

    def add(self, offset: int, accidental: str = FLAT) -> NoteName:
        name = NUMBER_TO_NOTES[accidental][(offset + self.offset) % 12]
        return NoteName(name[0], name[1:])

    @cached_property
    def offset(self) -> int:
        """In semitones from C"""
        accidentals = sum(1 if a == SHARP else -1 for a in self.accidentals)
        return NOTE_TO_NUMBER[self.name] + accidentals


@cache
def make_note(note_name: str) -> NoteName:
    if not (m := NOTE_RE.match(note_name)):
        raise ValueError(f"Cannot understand note {note_name}")

    name, accidentals, octave = m.groups()
    acc = canonical(accidentals)
    return Note(name, acc, int(octave)) if octave else NoteName(name, acc)


# TODO: get rid of the string format, base everything around note number
@dc.dataclass(frozen=True)
class Note(NoteName):
    octave: int = 0

    def __repr__(self) -> str:
        return f"{super().__repr__()}{self.octave}"

    @staticmethod
    def from_name(note_name: str) -> Note:  # pyrefly: ignore[bad-overide]
        note = make_note(note_name)
        assert isinstance(note, Note)
        return note

    @staticmethod
    @cache
    def from_note_number(note_number: int, accidental: str = SHARP) -> Note:
        assert accidental in NUMBER_TO_NOTES, accidental

        octave, number = divmod(note_number, 12)
        octave += MIDI_ZERO_OCTAVE
        name = NUMBER_TO_NOTES[accidental][number]

        return Note(name=name[0], accidentals=name[1:], octave=octave)

    def closest(self, n: NoteName) -> Note:
        """Octaved version of n which is as close possible to self"""
        if isinstance(n, Note):
            return n
        off = self.offset - n.offset
        delta = 1 if off <= -5 else 0 if off <= 5 else -1
        assert -11 <= off <= 11, (off, n, delta)
        return Note(octave=self.octave + delta, **dc.asdict(n))

    def add(self, offset: int, accidental: str = SHARP) -> Note:
        return self.from_note_number(self.note_number + offset, accidental)

    @cached_property
    def note_number(self) -> int:
        return 12 * (self.octave - MIDI_ZERO_OCTAVE) + self.offset

    @cached_property
    def frequency(self) -> float:
        return 440.0 * 2 ** ((self.note_number - A4) / 12)
