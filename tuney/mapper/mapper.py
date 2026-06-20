from __future__ import annotations

from enum import Enum
from functools import cached_property
from math import floor
from string import ascii_letters, ascii_lowercase

import tyro
from pydantic import BaseModel

MIDDLE_NOTE: float = 63.5
DEFAULT_PLAYER_NOTE_OFFSET: int = 44
MAPPER_CENTER: float = MIDDLE_NOTE - DEFAULT_PLAYER_NOTE_OFFSET


def centered_note_number(index: int, span: int, offset: int) -> int:
    return floor(index - (span - 1) / 2 + MAPPER_CENTER + offset + 0.5)


def linear(m: Mapper) -> dict[str, int]:
    def char_to_number(index: int, c: str) -> int:
        span = m.length or len(m.alphabet_)
        if m.invert:
            index = len(m.alphabet_) - index - 1
        if m.length:
            index %= m.length
        return centered_note_number(index, span, m.offset)

    return {a: char_to_number(i, a) for i, a in enumerate(m.alphabet_)}


class Map(Enum):
    linear = (linear,)

    @classmethod
    def _missing_(cls, value: object) -> Map | None:
        return (
            cls[value] if isinstance(value, str) and value in cls.__members__ else None
        )

    def __call__(self, m: Mapper) -> dict[str, int]:
        return self.value[0](m)


class Limiter(Enum):
    wrap = 'wrap'
    reflect = 'reflect'
    reflect_repeat = 'reflect_repeat'

    @classmethod
    def _missing_(cls, value: object) -> Limiter | None:
        return (
            cls[value] if isinstance(value, str) and value in cls.__members__ else None
        )

    def __call__(self, note_number: int, range_limit: int, offset: int) -> int:
        if range_limit <= 0:
            return note_number

        low = centered_note_number(0, range_limit, offset)
        high = low + range_limit - 1
        match self:
            case Limiter.wrap:
                return low + (note_number - low) % range_limit
            case Limiter.reflect:
                if range_limit == 1:
                    return low
                period = range_limit * 2 - 2
                wrapped = (note_number - low) % period
                return (
                    low + wrapped if wrapped < range_limit else low + period - wrapped
                )
            case Limiter.reflect_repeat:
                period = range_limit * 2
                wrapped = (note_number - low) % period
                return (
                    low + wrapped
                    if wrapped < range_limit
                    else high - wrapped % range_limit
                )


class Mapper(BaseModel, frozen=True):
    map: tyro.conf.Suppress[Map] = Map.linear

    # Characters mapped to note numbers, or the default alphabet if empty
    alphabet: str | None = None

    # Number of note numbers to cycle through; zero uses the full alphabet
    length: int = 0

    # Treat uppercase and lowercase characters as distinct
    case_sensitive: bool = True

    # Reverse the order of mapped note numbers
    invert: bool = False

    # Offset from the center of the mapped note range
    offset: int = 0

    # Limit pitch range to this many notes
    range_limit: int = 60

    # What to do when mapped notes are outside the pitch range
    limiter: Limiter = Limiter.wrap

    @cached_property
    def alphabet_(self) -> str:
        return self.alphabet or (
            ascii_letters if self.case_sensitive else ascii_lowercase
        )

    def __call__(self, k: str) -> int | None:
        return self.char_to_number.get(k if self.case_sensitive else k.lower())

    @cached_property
    def char_to_number(self) -> dict[str, int]:
        return {
            char: self.limiter(note_number, self.range_limit, self.offset)
            for char, note_number in self.map(self).items()
        }
