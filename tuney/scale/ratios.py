from __future__ import annotations

from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, model_validator
from ufor.number import Number
from ufor.scala import parse_scala, scala_text
from ufor.tuning import RatioTable

from ..config.annotations import Display
from ..config.text_file import read_text_file
from . import evaluate


class Ratios(BaseModel):
    #: Ratio expressions for each step in the scale
    text: Annotated[str, Display(row=0, width=24)] = ''

    #: Name of this ratio scale
    name: Annotated[str, Display(row=1, column=0)] = ''

    #: Description of this ratio scale
    desc: Annotated[str, Display(row=1, column=1, width=24)] = ''

    @model_validator(mode='after')
    def _validate_text(self) -> Ratios:
        if not _split_expression_text(self.text):
            raise ValueError('No tuning ratios configured')
        return self

    @cached_property
    def definition(self) -> RatioTable:
        entries = [str(i) for i in self.ratios]
        return RatioTable(
            values=['1', *entries[:-1]],
            repeat_ratio=entries[-1],
            name=self.name,
            desc=self.desc,
        )

    def __call__(self, note_delta: int) -> Number:
        return self.definition(note_delta)

    @cached_property
    def length(self) -> int:
        return len(self.ratios)

    @cached_property
    def ratios(self) -> list[Number]:
        ratios = evaluate.evaluate_all(_split_expression_text(self.text))
        if any(i <= 0 for i in ratios):
            raise ValueError('Tuning ratios must be positive')
        return ratios

    @staticmethod
    def read_scala_file(path: Path, name: str = '') -> Ratios:
        definition = parse_scala(read_text_file(path), name=name or path.name)
        assert definition.repeat_ratio is not None
        return Ratios.from_strings(
            [*definition.values[1:], definition.repeat_ratio],
            name=definition.name,
            desc=definition.desc,
        )

    @staticmethod
    def from_strings(strings: Iterable[str], name: str = '', desc: str = '') -> Ratios:
        return Ratios(text='; '.join(strings), name=name, desc=desc)

    def write_scala_file(self, path: Path, encoding: str = 'latin-1') -> None:
        path.write_text(scala_text(self.definition), encoding=encoding)


def _split_expression_text(text: str) -> list[str]:
    return [s for i in text.split(';') if (s := i.strip())]
