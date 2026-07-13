from __future__ import annotations

from enum import StrEnum, auto
from functools import cached_property
from math import floor
from string import ascii_lowercase, ascii_uppercase
from typing import Annotated

import tyro
from pydantic import BaseModel, Field

from ..config.display import Beginner, Display, Numeric
from ..config.named_enum import NamedEnum
from ..config.tyro_option import tyro_option

MIDDLE_NOTE: float = 63.5
DEFAULT_PLAYER_NOTE_OFFSET: int = 44
MAPPER_CENTER: float = MIDDLE_NOTE - DEFAULT_PLAYER_NOTE_OFFSET
DEFAULT_ALPHABET: str = ascii_uppercase + ascii_lowercase


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


class Map(NamedEnum):
    linear = (linear,)

    def __call__(self, m: Mapper) -> dict[str, int]:
        return self.value[0](m)


class Limiter(StrEnum):
    # Notes wrap around from the start when they reach the edge
    wrap = auto()

    # Notes reflect from the edge and start moving in the other direction.
    # The edge note is only played once.
    reflect = auto()

    # Notes reflect from the edge and start moving in the other direction.
    # The edge note is played twice so that all the notes are equally played
    reflect_repeat = auto()

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


class Mapper(BaseModel):
    map: tyro.conf.Suppress[Map] = Map.linear

    # Characters mapped to note numbers, or the default alphabet if empty
    alphabet: Annotated[
        str | None,
        tyro_option('-a'),
        Beginner,
        Display(row=0),
    ] = None

    # Number of note numbers to cycle through; zero uses the full alphabet
    length: Annotated[int, tyro_option('-l'), Display(row=1), Numeric(min=0)] = Field(
        0, ge=0
    )

    # Treat uppercase and lowercase characters as distinct
    case_sensitive: Annotated[bool, tyro_option('-C'), Display(column=4, row=1)] = True

    # Reverse the order of mapped note numbers
    invert: Annotated[bool, tyro_option('-I'), Display(column=5, row=1)] = False

    # Offset from the center of the mapped note range
    offset: Annotated[
        int,
        tyro_option('-O', name='mapper-offset'),
        Display(column=1, row=1),
        Numeric(),
    ] = 0

    # Limit pitch range to this many notes
    range_limit: Annotated[
        int, tyro_option('-r'), Beginner, Display(column=2, row=1), Numeric()
    ] = 60

    # What to do when mapped notes are outside the pitch range
    limiter: Annotated[Limiter, tyro_option('-L'), Display(column=3, row=1)] = (
        Limiter.wrap
    )

    @cached_property
    def alphabet_(self) -> str:
        return self.alphabet or (
            DEFAULT_ALPHABET if self.case_sensitive else ascii_lowercase
        )

    def __call__(self, k: str) -> int | None:
        return self.char_to_number.get(k if self.case_sensitive else k.lower())

    @cached_property
    def char_to_number(self) -> dict[str, int]:
        return {
            char: self.limiter(note_number, self.range_limit, self.offset)
            for char, note_number in self.map(self).items()
        }
