from __future__ import annotations

import math
from collections.abc import Callable

from pydantic import BaseModel, GetCoreSchemaHandler, model_validator
from pydantic_core import CoreSchema


class _Base(BaseModel, frozen=True):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: object, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return handler(source)


class Display(_Base, frozen=True):
    column: int = 0
    row: int | None = None
    width: int | None = None


class Options(_Base, frozen=True):
    options: Callable[[], list[str]]

    def __init__(self, options: Callable[[], list[str]]) -> None:
        super().__init__(**{'options': options})


class Numeric(_Base, frozen=True):
    min: float | None = None
    max: float | None = None
    dial: bool = False
    log: bool = False
    # Number of decimal places to display
    decimals: int | None = None
    # How much to increment or decrement when clicking on the arrows.
    # A percentage for exponential, an absolute value otherwise.
    inc: float | None = None

    @model_validator(mode='after')
    def validate_log_range(self) -> Numeric:
        if self.dial and (self.min is None or self.max is None):
            raise ValueError('Numeric dials require min and max')
        if self.log and (
            self.min is None or self.max is None or self.min <= 0 or self.max <= 0
        ):
            raise ValueError('Logarithmic dials require positive min and max')
        if self.inc is not None and self.inc <= 0:
            raise ValueError('Numeric increments must be positive')
        return self

    def spin_to_dial(self, value: float) -> int:
        assert self.min is not None
        assert self.max is not None
        if self.log:
            r = math.log(value / self.min) * 100 / math.log(self.max / self.min)
        else:
            r = (value - self.min) * 100 / (self.max - self.min)
        return round(r)

    def dial_to_spin(self, value: int) -> float:
        assert self.min is not None
        assert self.max is not None
        if self.log:
            return self.min * (self.max / self.min) ** (value / 100)
        return self.min + value * (self.max - self.min) / 100

    @property
    def displayed_decimals(self) -> int:
        return 3 if self.decimals is None else self.decimals

    @property
    def increment(self) -> float:
        return 0.1 if self.inc is None else self.inc

    def step(self, value: float, steps: int) -> float:
        if not self.log:
            return value + steps * self.increment
        assert self.min is not None
        multiplier = (1 + self.increment / 100) ** abs(steps)
        if steps > 0:
            return value * multiplier
        return value / multiplier


class Hidden:
    pass


class General:
    pass


class Beginner:
    pass
