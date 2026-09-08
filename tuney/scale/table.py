from __future__ import annotations

from decimal import Decimal
from functools import cached_property
from typing import Annotated

from pydantic import BaseModel
from reccy.configuration import units
from ufor.number import Number
from ufor.tuning import FrequencyTable

from ..config.annotations import Display
from . import evaluate

type Frequency = float  # Must be non-negative


class Table(BaseModel):
    #: Absolute frequency expressions, indexed by note number
    text: Annotated[str, Display(row=0, width=24)] = ''

    @cached_property
    def definition(self) -> FrequencyTable:
        if not self.values:
            raise ValueError('No frequency table configured')
        return FrequencyTable(values=[str(i) for i in self.values])

    def __call__(self, note_delta: int) -> Frequency:
        return float(self.definition(note_delta))

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
