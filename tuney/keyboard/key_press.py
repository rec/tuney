from __future__ import annotations

from typing import NamedTuple

from pynput.keyboard import Key, KeyCode

type KeyType = Key | KeyCode


class KeyPress(NamedTuple):
    key: KeyType
    is_press: bool = True


class CharPress(NamedTuple):
    char: str
    is_press: bool = True
