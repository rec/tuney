from __future__ import annotations

from enum import StrEnum, auto

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


class Accidentals(StrEnum):
    none = auto()
    whole = auto()
    half = auto()


class AccidentalNames:
    def __init__(self, accidentals: Accidentals) -> None:
        self.accidentals = accidentals

    @property
    def symbols(self) -> str:
        return {
            Accidentals.none: '',
            Accidentals.whole: FLAT + SHARP,
            Accidentals.half: ACCIDENTALS,
        }[self.accidentals]

    def canonical(self, s: str) -> str:
        for k, v in CANONICAL.items():
            s = s.replace(k, v)
        return s

    def name(self, note: str, offset: int, use_sharp: bool) -> str:
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
        raise AssertionError(f'Unknown accidentals {self.accidentals}')

    def flat_sharp_names(
        self, note: str, next_note: str, interval: int, offset: int
    ) -> tuple[str, str]:
        flat = self.name(next_note, interval - offset, False)
        sharp = self.name(note, offset, True)
        if self.accidentals == Accidentals.half and offset > interval // 2:
            return sharp, flat
        return flat, sharp

    def split_note(self, s: str, names: str) -> tuple[str, str]:
        if s and s[0] in names:
            note = s[0]
            s = s[1:]
            while (
                s
                and (accidental := ACCIDENTAL_CANONICAL.get(s[0]))
                and accidental in self.symbols
            ):
                note += accidental
                s = s[1:]
            return note, s
        raise ValueError(f'Bad number {s=}')
