from collections.abc import Callable

from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import CoreSchema


class Display(BaseModel, frozen=True):
    hidden: bool = False
    general: bool = False
    beginner: bool = False
    column: int = 0
    row: int | None = None
    width: int | None = None
    step: float = 0.1
    dial: bool = False
    dial_minimum: float = 0.0
    dial_maximum: float = 4.0
    options: Callable[[], list[str]] | None = None

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: object, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return handler(source)
