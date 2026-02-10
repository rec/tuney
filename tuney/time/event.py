from __future__ import annotations

import dataclasses as dc
import heapq
import time
from collections.abc import Callable
from typing import Any

from ..types import Seconds

MAX_WAIT: Seconds = 0.01


@dc.dataclass
class Event[Data]:
    timestamp: Seconds
    data: Data

    def __lt__(self, other: Event) -> bool:
        return self.timestamp < other.timestamp


@dc.dataclass
class Runner[Data]:
    events: list[Event[Data]]
    callback: Callable[..., Any]

    _running: bool = False

    def __post_init__(self) -> None:
        heapq.heapify(self.events)

    def run(self) -> None:
        self._running = True
        while self._running:
            while self.events and self.events[0].timestamp <= time.time():
                self.callback(d := heapq.heappop(self.events).data)
                print('run', d)

            if self.events:
                time.sleep(min(MAX_WAIT, self.events[0].timestamp - time.time()))
            else:
                self.stop()

    def stop(self) -> None:
        self._running = False


def demo() -> None:
    def event() -> Event[float]:
        import random

        t = timestamp + random.uniform(0, 1)
        return Event(t, t - timestamp)

    timestamp = time.time()
    Runner([event() for _ in range(10)], print).run()


if __name__ == '__main__':
    demo()
