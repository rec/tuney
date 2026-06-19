from __future__ import annotations

from enum import Enum
from functools import cached_property
from string import ascii_letters, ascii_lowercase

import tyro
from pydantic import BaseModel


def linear(m: Mapper) -> dict[str, int]:
    def char_to_number(index: int, c: str) -> int:
        if m.invert:
            index = len(m.alphabet_) - index - 1
        if m.length:
            index %= m.length
        return index + m.offset

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

    # Offset added to mapped note numbers
    offset: int = 0

    @cached_property
    def alphabet_(self) -> str:
        return self.alphabet or (
            ascii_letters if self.case_sensitive else ascii_lowercase
        )

    def __call__(self, k: str) -> int | None:
        return self.char_to_number.get(k if self.case_sensitive else k.lower())

    @cached_property
    def char_to_number(self) -> dict[str, int]:
        return self.map(self)
