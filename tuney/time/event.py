from __future__ import annotations

import dataclasses as dc
import heapq
import time
from threading import Lock
from typing import Any, Callable, NamedTuple, Sequence

from . import Seconds

MAX_WAIT: Seconds = 0.01


class Event(NamedTuple):
    timestamp: Seconds
    callback: Callable[[], Any]

    def __lt__(self, other: Event) -> bool:
        return self.timestamp < other.timestamp


@dc.dataclass
class Runner:
    events: list[Event]
    keep_running: bool = False

    _running: bool = False

    def __post_init__(self) -> None:
        heapq.heapify(self.events)

    def run(self) -> None:
        self._running = True
        while self._running:
            events = []
            timestamp = time.time()
            while self.events and self.events[0].timestamp <= timestamp:
                events.append(heapq.heappop(self.events))

            for e in events:
                e.callback()

            if self.events:
                time.sleep(max(MAX_WAIT, self.events[0].timestamp - time.time()))
            elif self.keep_running:
                time.sleep(MAX_WAIT)
            else:
                self.stop()

    def stop(self) -> None:
        self._running = False


def demo() -> None:
    def event() -> Event:
        import random

        t = timestamp + random.uniform(0, 1)
        return Event(t, lambda: print(t - timestamp))

    timestamp = time.time()
    Runner([event() for _ in range(10)]).run()


if __name__ == "__main__":
    demo()
