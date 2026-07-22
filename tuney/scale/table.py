from __future__ import annotations

from functools import cached_property
from typing import Annotated

from pydantic import BaseModel

from ..config.annotations import Display
from ..config.tyro_option import tyro_option
from . import Number, evaluate

type Frequency = float  # Must be non-negative


class Table(BaseModel):
    #: Absolute frequency expressions, indexed by note number
    text: Annotated[str, tyro_option(), Display(row=0, width=24)] = ''

    def __call__(self, note_delta: int) -> Frequency:
        if not (values := self.values):
            raise ValueError('No frequency table configured')
        return values[note_delta % len(values)]

    @cached_property
    def values(self) -> list[Frequency]:
        values = [float(i) for i in _evaluate_text(self.text)]
        if any(i <= 0 for i in values):
            raise ValueError('Frequency table values must be positive')
        return values


def _evaluate_text(text: str) -> list[Number]:
    return evaluate.evaluate_all(i.strip() for i in text.split(';') if i.strip())
