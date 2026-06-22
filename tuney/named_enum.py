from __future__ import annotations

from enum import Enum
from typing import Self


class NamedEnum(Enum):
    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if isinstance(value, str) and value in cls.__members__:
            return cls[value]
