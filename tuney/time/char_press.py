from __future__ import annotations

from pydantic import BaseModel, field_validator

from . import Seconds


class CharPress(BaseModel):
    char: str
    is_press: bool = True
    time: Seconds

    def __init__(
        self, char: str = '', is_press: bool = True, time: Seconds = 0
    ) -> None:
        super().__init__(char=char, is_press=is_press, time=time)

    def __lt__(self, other: CharPress) -> bool:
        return self.time < other.time

    @field_validator('time')
    @classmethod
    def _validate_time(cls, time: Seconds) -> Seconds:
        return max(0.0, time)
