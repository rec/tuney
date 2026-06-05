from __future__ import annotations

from functools import singledispatchmethod
from typing import NamedTuple

from pydantic import BaseModel
from pynput.keyboard import Key, KeyCode

from . import WHITESPACE


class KeyPress(NamedTuple):
    key: Key | KeyCode
    is_press: bool = True


class CharPress(NamedTuple):
    char: str
    is_press: bool = True
