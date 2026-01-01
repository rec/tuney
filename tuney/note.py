from __future__ import annotations

import dataclasses as dc
import re


ACCIDENTAL_DICT = {"#": "♯", "b": "♭", "♭": "♭", "♯": "♯"}
ACCIDENTALS = "".join(ACCIDENTAL_DICT)

NOTE_RE = re.compile(rf"([A-G])([{ACCIDENTALS}]*)(-?\d*)")


def canonical(s: str) -> str:
    for k, v in ACCIDENTAL_DICT.items():
        s = s.replace(k, v)
    return s


@dc.dataclass
class Note:
    name: str
    accidentals: str = ""
    octave: int | None = None

    def __repr__(self) -> str:
        octave = "" if self.octave is None else self.octave
        return f"{self.name}{self.accidentals}{octave}"

    @staticmethod
    def make(note_name: str) -> Note:
        if m := NOTE_RE.match(note_name):
            name, accidentals, octave = m.groups()
            return Note(name, canonical(accidentals), int(octave) if octave else None)

        raise ValueError(f"Cannot understand note {note_name}")
