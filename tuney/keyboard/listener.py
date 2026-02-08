from __future__ import annotations

import dataclasses as dc
from functools import cached_property, wraps
from typing import Any

from pynput import keyboard

from .key_types import Callback, Key, KeyAction
from .modifiers import KeyPress, Modifiers


@dc.dataclass
class KeyboardListener:
    callback: Callback
    stop_key: keyboard.Key | None = None

    _running: bool = False

    @cached_property
    def listener(self) -> keyboard.Listener:
        return _make_listener(self)

    @cached_property
    def modifiers(self) -> Modifiers:
        return Modifiers()

    def on_press(self, key: Key | None) -> bool | None:
        if not self._running or key == self.stop_key:
            return False
        self._on(key, True)

    def on_release(self, key: Key | None) -> None:
        self._on(key, False)

    def start(self) -> None:
        self._running = True
        self.listener.__enter__()

    def join(self) -> None:
        self.listener.join()

    def stop(self) -> None:
        self._running = False
        self.listener.stop()

    def _on(self, key: Key | None, is_press: bool) -> None:
        self.modifiers = self.modifiers.apply(KeyPress(key, is_press))
        if not self.modifiers.is_command and (char := getattr(key, 'char', '')):
            self.callback(KeyAction(char, is_press))


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
    warning_ = log.warning

    @wraps(warning_)
    def warning(a: str, *args: Any, **kwargs: Any) -> None:
        if not a.strip() or a.replace(BOGUS_WARNING, '').strip() or args or kwargs:
            warning_(a, *args, **kwargs)

    log.warning = warning
    return listener
