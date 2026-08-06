from __future__ import annotations

from pydantic import BaseModel, PrivateAttr, field_validator

from .units import Seconds


class CharPress(BaseModel):
    char: str
    is_press: bool = True
    time: Seconds
    _pressed_char: str = PrivateAttr('')

    def __init__(
        self, char: str = '', is_press: bool = True, time: Seconds = 0
    ) -> None:
        super().__init__(char=char, is_press=is_press, time=time)

    def __lt__(self, other: CharPress) -> bool:
        return self.time < other.time

    @property
    def pressed_char(self) -> str:
        return self._pressed_char

    def with_pressed_char(self, pressed_char: str) -> CharPress:
        self._pressed_char = pressed_char
        return self

    @field_validator('time')
    @classmethod
    def _validate_time(cls, time: Seconds) -> Seconds:
        return max(0.0, time)
