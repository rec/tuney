from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum, auto
from functools import cached_property
from math import floor
from string import ascii_lowercase, ascii_uppercase
from typing import Annotated

import tyro
from pydantic import BaseModel, field_validator, model_validator

from ..config.display import Beginner, Display, Hidden, Numeric
from ..config.named_enum import NamedEnum
from ..config.tyro_option import tyro_option
from .language import alphabet_for_language, known_language

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
    wrap = auto()
    reflect = auto()
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

    # Language tag whose alphabet is used when alphabet is empty
    language: Annotated[str | None, tyro_option(), Hidden] = None

    # Number of note numbers to cycle through; zero uses the full alphabet
    length: Annotated[int, tyro_option('-l'), Display(row=1), Numeric()] = 0

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

    @model_validator(mode='before')
    @classmethod
    def _fill_alphabet_from_language(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data
        values: dict[str, object] = {str(k): v for k, v in data.items()}
        language = values.get('language')
        case_sensitive = values.get('case_sensitive', True)
        if language is not None and not isinstance(language, str):
            return data
        if not isinstance(case_sensitive, bool):
            return data
        generated_alphabets = {
            DEFAULT_ALPHABET,
            ascii_lowercase,
            alphabet_for_language(language, True) or DEFAULT_ALPHABET,
            alphabet_for_language(language, False) or ascii_lowercase,
        }
        if (
            values.get('alphabet') is not None
            and values['alphabet'] not in generated_alphabets
        ):
            return data
        alphabet = alphabet_for_language(language, case_sensitive) or (
            DEFAULT_ALPHABET if case_sensitive else ascii_lowercase
        )
        return values | {'alphabet': alphabet}

    @field_validator('language')
    @classmethod
    def _validate_language(cls, language: str | None) -> str | None:
        if language is not None and not known_language(language):
            raise ValueError(f'Unknown language: {language}')
        return language

    @cached_property
    def alphabet_(self) -> str:
        return (
            self.alphabet
            or alphabet_for_language(self.language, self.case_sensitive)
            or (DEFAULT_ALPHABET if self.case_sensitive else ascii_lowercase)
        )

    def __call__(self, k: str) -> int | None:
        return self.char_to_number.get(k if self.case_sensitive else k.lower())

    @cached_property
    def char_to_number(self) -> dict[str, int]:
        return {
            char: self.limiter(note_number, self.range_limit, self.offset)
            for char, note_number in self.map(self).items()
        }
