from __future__ import annotations

from typing import NamedTuple


class CharPress(NamedTuple):
    char: str
    is_press: bool = True
