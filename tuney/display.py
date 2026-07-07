from collections.abc import Callable

from pydantic import BaseModel, GetCoreSchemaHandler
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
    options: Callable[[], list[str]] | None = None


class Dial(_Base, frozen=True):
    min: float = 0.0
    max: float = 4.0

    def dial_value(self, value: float) -> int:
        return round((float(value) - self.min) * 100 / (self.max - self.min))

    def spin_value(self, value: int) -> float:
        return self.min + value * (self.max - self.min) / 100


class Hidden(_Base, frozen=True):
    pass


class General(_Base, frozen=True):
    pass


class Beginner(_Base, frozen=True):
    pass
