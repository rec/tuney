from __future__ import annotations

__all__ = ['KeyPress', 'KeyboardListener']

from .listener import KeyboardListener, KeyPress

if __name__ == '__main__':
    KeyboardListener(print).run()
