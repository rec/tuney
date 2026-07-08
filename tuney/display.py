from __future__ import annotations

from collections.abc import Callable
from math import log as logarithm

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
    step: float = 0.1


class Options(_Base, frozen=True):
    options: Callable[[], list[str]]

    def __init__(self, options: Callable[[], list[str]]) -> None:
        super().__init__(**{'options': options})


class Dial(_Base, frozen=True):
    min: float = 0.0
    max: float = 4.0
    log: bool = False

    @model_validator(mode='after')
    def validate_log_range(self) -> Dial:
        if self.log and (self.min <= 0 or self.max <= 0):
            raise ValueError('Logarithmic dials require positive min and max')
        return self

    def spin_to_dial(self, value: float) -> int:
        value = float(value)
        if self.log:
            return round(
                logarithm(value / self.min) * 100 / logarithm(self.max / self.min)
            )
        return round((value - self.min) * 100 / (self.max - self.min))

    def dial_to_spin(self, value: int) -> float:
        if self.log:
            return self.min * (self.max / self.min) ** (value / 100)
        return self.min + value * (self.max - self.min) / 100


class Hidden:
    pass


class General:
    pass


class Beginner:
    pass
