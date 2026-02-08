from abc import ABC, abstractmethod
from threading import Thread


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
        t = Thread(target=self.run)
        t.start()
        return t

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
