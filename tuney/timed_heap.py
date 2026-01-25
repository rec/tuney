from __future__ import annotations

import dataclasses as dc
import heapq
import time
from threading import Lock
from typing import Any, Callable

from . import Seconds

MAX_WAIT: Seconds = 0.01


@dc.dataclass(frozen=True)
class Event:
    timestamp: Seconds
    callback: Callable[[], Any]

    def __lt__(self, other: Event) -> bool:
        return self.timestamp < other.timestamp


@dc.dataclass
class TimedHeap:
    heap: list[Event] = dc.field(default_factory=list)

    running: bool = False
    keep_running: bool = False

    _lock: Lock = dc.field(default_factory=Lock)

    def __post_init__(self) -> None:
        heapq.heapify(self.heap)

    def push(self, event: Event) -> None:
        with self._lock:
            heapq.heappush(self.heap, event)

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        self.running = True
        while self.running:
            events = []
            with self._lock:
                timestamp = time.time()
                while self.heap and self.heap[0].timestamp <= timestamp:
                    events.append(heapq.heappop(self.heap))

            for e in events:
                e.callback()

            if self.heap:
                time.sleep(min(MAX_WAIT, self.heap[0].timestamp - time.time()))
            elif self.keep_running:
                time.sleep(MAX_WAIT)
            else:
                self.stop()


def demo() -> None:
    import random

    random.seed(23)
    timestamp = time.time()

    def event() -> Event:
        t = timestamp + random.uniform(0, 5)
        return Event(t, lambda: print(t - timestamp))

    TimedHeap([event() for _ in range(8)]).run()


if __name__ == "__main__":
    demo()
