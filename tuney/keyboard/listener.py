from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, Literal

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from ..runnable import Runnable
from ..char_press import CharPress
from .modifiers import Modifiers

WHITESPACE = {Key.space: ' ', Key.enter: '\n', Key.backspace: '\b'}


class KeyboardListener(Runnable):
    def __init__(
        self,
        callback: Callable[[CharPress], Any],
        deduplicate_keys: bool = True,
    ) -> None:
        self.callback = callback
        self.listener = _make_listener(self)
        self.modifiers = Modifiers(0)
        self.deduplicate_keys = deduplicate_keys
        self.held_keys = set()

    def on_press(self, key: Key | KeyCode | None) -> None | Literal[False]:
        return self.is_running and self._on(key, True)

    def on_release(self, key: Key | KeyCode | None) -> None | Literal[False]:
        return self.is_running and self._on(key, False)

    def _on(self, key: Key | KeyCode, is_press: bool) -> None:
        if self.deduplicate_keys:
            if not is_press:
                self.held_keys.discard(key)
            elif key in self.held_keys:
                return
            else:
                self.held_keys.add(key)
        if isinstance(key, Key):
            self.modifiers = self.modifiers.apply(key, is_press)

        c = WHITESPACE.get(key, getattr(key, 'char', ''))
        if c and (not is_press or not self.modifiers.is_command):
            self.callback(CharPress(c, is_press, time=time.time()))

    def _run(self) -> None:
        self.listener.__enter__()
        self.listener.join()

    def stop(self) -> None:
        super().stop()
        self.listener.stop()


def _make_listener(kl: KeyboardListener) -> keyboard.Listener:
    listener = keyboard.Listener(
        on_press=kl.on_press,
        on_release=kl.on_release,
    )
    log = getattr(listener, '_log', None)
    if not (log and hasattr(listener, 'IS_TRUSTED')):
        return listener

    # Work around a bogus warning in pynput and Darwin
    BOGUS_WARNING = (
        'This process is not trusted! Input event monitoring will not be possible'
        ' until it is added to accessibility clients.'
    )
    warning = log.warning

    @wraps(warning)
    def warning_(a: str, *args: Any, **kwargs: Any) -> None:
        if not a.strip() or a.replace(BOGUS_WARNING, '').strip() or args or kwargs:
            warning(a, *args, **kwargs)

    log.warning = warning_
    return listener


def main() -> None:
    KeyboardListener(print, True).run()


def time_keyboard() -> None:
    def key_callback(k):
        if k.is_press:
            nonlocal now
            old, now = now, time.time()
            print(now - old)

    now = time.time()
    KeyboardListener(key_callback).run()


if __name__ == '__main__':
    # main()
    time_keyboard()
