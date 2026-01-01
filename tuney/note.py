from __future__ import annotations

import dataclasses as dc


@dc.dataclass
class Note:
    name: str
    accidental: str = ""
    octave: int | None = None

    def __repr__(self) -> str:
        octave = "" if self.octave is None else self.octave
        return f"{self.name}{self.accidental}{octave}"

    @staticmethod
    def make(note_name: str) -> Note:
        if 1 <= len(n := note_name) <= 3 and "A" <= (name := n[0]) <= "G":
            n = n[1:]
            accidental = ""
            octave = None

            if n and n[-1].isnumeric():
                octave = int(n[-1])
                n = n[:-1]
            if n and n[0] in "#b":
                accidental = n[0]
                n = n[1:]
            if not n:
                return Note(name, accidental, octave)

        raise ValueError(f"Cannot understand note {note_name}")
