import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from threading import Thread
from typing import Any

from .platform_info import is_frozen, log_exception


def start_thread(target: Callable[[], Any], daemon: bool = True) -> Thread:
    """Start a thread and return it"""

    def catch_target() -> None:
        try:
            target()
        except Exception as error:
            if is_frozen():
                log_exception(error)
            else:
                traceback.print_exc()

    t = Thread(target=catch_target, daemon=daemon)
    t.start()
    return t


class Runnable(ABC):
    def run(self) -> None:
        self._running = True
        try:
            self._run()
        finally:
            self.stop()

    @abstractmethod
    def _run(self) -> None: ...

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> Thread:
        return start_thread(self.run)

    def stop(self) -> None:
        self._running = False

    _running: bool = False


class Loop(Runnable):
    def run(self) -> None:
        self._running = True
        try:
            while self._running:
                self._run()
        finally:
            self.stop()
