from __future__ import annotations

import dataclasses as dc
from collections.abc import Callable
from typing import TypeAlias

from pynput import keyboard


@dc.dataclass(frozen=True)
class KeyAction:
    char: str = ""
    is_press: bool = False


Key: TypeAlias = keyboard.Key | keyboard.KeyCode
Callback: TypeAlias = Callable[[KeyAction], None]


from .listener import KeyboardListener
from .queue import KeyboardQueue

if __name__ == "__main__":
    if True:
        KeyboardQueue(print).start()
    else:
        KeyboardListener(print).start()
