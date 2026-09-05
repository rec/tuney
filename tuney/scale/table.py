from __future__ import annotations

from decimal import Decimal
from functools import cached_property
from typing import Annotated

from pydantic import BaseModel
from reccy.configuration import units

from ..config.annotations import Display
from . import evaluate
from .number import Number

type Frequency = float  # Must be non-negative


class Table(BaseModel):
    #: Absolute frequency expressions, indexed by note number
    text: Annotated[str, Display(row=0, width=24)] = ''

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
    return [_evaluate_frequency(i.strip()) for i in text.split(';') if i.strip()]


def _evaluate_frequency(expression: str) -> Number:
    try:
        value = units.magnitude(expression, 'hertz')
        if not isinstance(value, (Decimal, float, int)):
            raise ValueError('Expected a hertz quantity')
        return float(value)
    except ValueError:
        return evaluate.evaluate(expression)
