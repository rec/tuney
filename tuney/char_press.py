from __future__ import annotations

from pydantic import BaseModel

from .types import Seconds


class CharPress(BaseModel, frozen=True):
    char: str
    is_press: bool = True
    time: Seconds

    def __init__(
        self, char: str = '', is_press: bool = True, time: Seconds = 0
    ) -> None:
        super().__init__(char=char, is_press=is_press, time=time)

    def __lt__(self, other: CharPress) -> bool:
        return self.time < other.time
