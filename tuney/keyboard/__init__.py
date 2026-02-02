from __future__ import annotations

__all__ = ["KeyAction", "KeyboardListener", "KeyboardQueue"]

from .key_types import KeyAction
from .listener import KeyboardListener
from .queue import KeyboardQueue

if __name__ == "__main__":
    if True:
        KeyboardQueue(print).start()
    else:
        KeyboardListener(print).start()
