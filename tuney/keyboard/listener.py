from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from functools import cached_property, wraps
from typing import Literal, Protocol

from ..app.runnable import Runnable
from ..time.char_press import CharPress
from .modifiers import Modifiers

WHITESPACE = {'space': ' ', 'enter': '\n', 'backspace': '\b'}
IGNORED_KEYS = {'caps_lock'}


class PynputListener(Protocol):
    def __enter__(self) -> object: ...

    def join(self) -> None: ...

    def stop(self) -> None: ...


class KeyboardListener(Runnable):
    def __init__(
        self,
        callback: Callable[[CharPress], object],
        deduplicate_keys: bool = True,
    ) -> None:
        self.callback = callback
        self.modifiers = Modifiers(0)
        self.deduplicate_keys = deduplicate_keys
        self.held_keys: set[Hashable | None] = set()

    @cached_property
    def listener(self) -> PynputListener:
        return _make_listener(self)

    def on_press(self, key: Hashable | None) -> None | Literal[False]:
        return self.is_running and self._on(key, True)

    def on_release(self, key: Hashable | None) -> None | Literal[False]:
        return self.is_running and self._on(key, False)

    def _on(self, key: Hashable | None, is_press: bool) -> None:
        if (key_name := str(getattr(key, 'name', ''))) in IGNORED_KEYS:
            return
        if self.deduplicate_keys:
            if not is_press:
                self.held_keys.discard(key)
            elif key in self.held_keys:
                return
            else:
                self.held_keys.add(key)
        if key_name:
            self.modifiers = self.modifiers.apply(key, is_press)

        if (c := WHITESPACE.get(key_name, getattr(key, 'char', ''))) and (
            not is_press or not self.modifiers.is_command
        ):
            self.callback(CharPress(c, is_press, time=time.time()))

    def _run(self) -> None:
        self.listener.__enter__()
        self.listener.join()

    def stop(self) -> None:
        super().stop()
        if 'listener' in self.__dict__:
            self.listener.stop()


def _make_listener(kl: KeyboardListener) -> PynputListener:
    from pynput import keyboard

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
    def warning_(a: str, *args: object, **kwargs: object) -> None:
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
