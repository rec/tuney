from __future__ import annotations

import dataclasses as dc
import heapq
import time
from collections.abc import Callable
from typing import Any, override

from ..runnable import Runnable
from ..types import Seconds

MAX_WAIT: Seconds = 0.01


@dc.dataclass
class Event[Data]:
    timestamp: Seconds
    data: Data

    def __lt__(self, other: Event) -> bool:
        return self.timestamp < other.timestamp


@dc.dataclass
class Runner[Data](Runnable):
    events: list[Event[Data]]
    callback: Callable[[Data], Any]

    def __post_init__(self) -> None:
        heapq.heapify(self.events)

    @override
    def _run(self) -> None:
        start = time.time()

        def next_time() -> float:
            return max(0, self.events[0].timestamp - time.time() + start)

        while self._running:
            while self.events and not next_time():
                self.callback(heapq.heappop(self.events).data)

            if self.events:
                time.sleep(min(MAX_WAIT, next_time()))
            else:
                self.stop()


def demo() -> None:
    def event() -> Event[float]:
        import random

        t = random.uniform(0, 2)
        return Event(t, t)

    Runner([event() for _ in range(16)], print).run()


if __name__ == '__main__':
    demo()
