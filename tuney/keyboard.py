from __future__ import annotations

import dataclasses as dc
import sys
import threading
import traceback

from functools import cached_property, wraps
from pynput import keyboard
from queue import Empty, Queue
from typing import Any, Callable, TypeAlias

OptionalKey: TypeAlias = keyboard.Key | keyboard.KeyCode | None


@dc.dataclass(frozen=True)
class KeyAction:
    char: str = ""
    is_press: bool = False

    def __bool__(self) -> bool:
        return bool(self.char)


Callback: TypeAlias = Callable[[KeyAction], None]


@dc.dataclass
class KeyboardListener:
    callback: Callback
    stop_key: keyboard.Key = keyboard.Key.esc

    @cached_property
    def listener(self) -> keyboard.Listener:
        return _make_listener(self)

    def on_press(self, key: OptionalKey) -> bool | None:
        if key == self.stop_key:
            return False
        self._on(key, True)

    def on_release(self, key: OptionalKey) -> None:
        self._on(key, False)

    def start(self) -> None:
        with self.listener:
            try:
                self.listener.join()
            finally:
                self.callback(KeyAction())

    def _on(self, key: OptionalKey, is_press: bool) -> None:
        if char := getattr(key, "char", ""):
            self.callback(KeyAction(char, is_press))


@dc.dataclass
class KeyboardQueue:
    callback: Callback
    timeout: float = 0.01
    running: bool = False

    def start(self) -> None:
        self.running = True
        try:
            self._thread.start()
            self._listener.start()
        finally:
            self.running = False

        self._thread.join()

    @cached_property
    def _listener(self) -> KeyboardListener:
        return KeyboardListener(self._queue.put)

    def _target(self) -> None:
        try:
            while self.running:
                try:
                    key_action = self._queue.get(timeout=self.timeout)
                except Empty:
                    continue
                if not key_action:
                    break
                self.callback(key_action)
            self.callback(KeyAction())
        except Exception:
            print("THREAD TERMINATED", file=sys.stderr)
            traceback.print_exc()

    @cached_property
    def _thread(self) -> threading.Thread:
        return threading.Thread(target=self._target)

    @cached_property
    def _queue(self) -> Queue[KeyAction]:
        return Queue()


def _make_listener(kl: KeyboardListener) -> keyboard.Listener:
    listener = keyboard.Listener(
        on_press=kl.on_press,
        on_release=kl.on_release,
    )
    log = getattr(listener, "_log", None)
    if not (log and hasattr(listener, "IS_TRUSTED")):
        return listener

    # Work around a bogus warning in pynput and Darwin
    BOGUS_WARNING = (
        "This process is not trusted! Input event monitoring will not be possible"
        " until it is added to accessibility clients."
    )
    warning_ = log.warning

    @wraps(warning_)
    def warning(a: str, *args: Any, **kwargs: Any) -> None:
        if not a.strip() or a.replace(BOGUS_WARNING, "").strip() or args or kwargs:
            warning_(a, *args, **kwargs)

    log.warning = warning
    return listener


if __name__ == "__main__":
    if True:
        KeyboardQueue(print).start()
    else:
        KeyboardListener(print).start()
