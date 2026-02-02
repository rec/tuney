from __future__ import annotations

import dataclasses as dc
import sys
import threading
import time
import traceback
from collections.abc import Callable
from functools import cached_property, wraps
from queue import Empty, Queue
from typing import Any, TypeAlias

from pynput import keyboard

from . import Callback, Key, KeyAction
from .listener import KeyboardListener


@dc.dataclass
class KeyboardQueue:
    callback: Callback
    timeout: float = 0.01
    running: bool = False

    def start(self) -> None:
        self.running = True
        threading.Thread(target=self._target).start()
        self._listener.start()

    def stop(self) -> None:
        self.running = False
        self._listener.stop()

    def join(self) -> None:
        # TODO: shouldn't I stop first?
        try:
            self._listener.join()
        finally:
            self.stop()

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
    def _queue(self) -> Queue[KeyAction]:
        return Queue()


def time_keyboard() -> None:
    def key_callback(k):
        if k.is_press:
            nonlocal now
            old, now = now, time.time()
            print(now - old)

    now = time.time()
    kq = KeyboardQueue(key_callback)
    kq.start()


def report() -> None:
    def key_callback(k):
        if k.is_press:
            print(k)

    now = time.time()
    kq = KeyboardQueue(key_callback)
    kq.start()


if __name__ == "__main__":
    report()
    # time_keyboard()
