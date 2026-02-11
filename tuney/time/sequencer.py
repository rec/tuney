from __future__ import annotations

import dataclasses as dc
import heapq
import time
from collections.abc import Callable
from typing import Any, override

from tuney.runnable import Runnable
from tuney.time import Event
from tuney.types import Milliseconds, Seconds

SEC_IN_MS = 1000.0

MAX_WAIT: Milliseconds = 100


@dc.dataclass
class Sequencer[Data](Runnable):
    events: list[Event[Data]]
    callback: Callable[[Data | None], Any]

    def __post_init__(self) -> None:
        heapq.heapify(self.events)

    @override
    def _run(self) -> None:
        start: Seconds = time.time()

        def elapsed() -> Milliseconds:
            return (time.time() - start) * SEC_IN_MS

        def next_time() -> Milliseconds:
            return max(0, self.events[0].timestamp - elapsed())

        try:
            while self._running:
                while self.events and not next_time():
                    self.callback(heapq.heappop(self.events).data)
                if self.events:
                    time.sleep(min(MAX_WAIT, next_time()) / 1000.0)
                else:
                    self.stop()
        finally:
            self.callback(None)


def demo() -> None:
    def event() -> Event[float]:
        import random

        t = random.uniform(0, 2)
        return Event(t, t)

    Sequencer([event() for _ in range(16)], print).run()


if __name__ == '__main__':
    demo()
