from abc import ABC, abstractmethod


class Runnable(ABC):
    def run(self) -> None:
        self._running = True
        try:
            self._run()
        finally:
            self.stop()

    @property
    def is_running(self) -> bool:
        return self._running

    def stop(self) -> None:
        self._running = False

    @abstractmethod
    def _run(self) -> None: ...

    _running: bool = False
