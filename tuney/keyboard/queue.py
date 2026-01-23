from __future__ import annotations

import dataclasses as dc
import sys
import threading
import traceback
from functools import cached_property, wraps
from queue import Empty, Queue
from typing import Any, Callable, TypeAlias

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
        self._thread.start()
        self._listener.start()

    def join(self) -> None:
        try:
            self._listener.join()
        finally:
            self.running = False

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
