from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


class NamedEnum(Enum):
    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if isinstance(value, str) and value in cls.__members__:
            return cls[value]

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {'enum': list(cls.__members__), 'title': cls.__name__, 'type': 'string'}
