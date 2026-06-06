from __future__ import annotations

import dataclasses as dc
import heapq
import time
from collections.abc import Callable
from typing import Any, override

from ..runnable import Runnable
from ..types import Milliseconds, Seconds
from .time_data import TimeData

SEC_IN_MS = 1000.0

MAX_WAIT: Milliseconds = 100


@dc.dataclass
class Sequencer[Data](Runnable):
    time_data: list[TimeData[Data]]
    callback: Callable[[Data | None], Any]

    def __post_init__(self) -> None:
        heapq.heapify(self.time_data)

    @override
    def _run(self) -> None:
        start: Seconds = time.time()

        def elapsed() -> Milliseconds:
            return (time.time() - start) * SEC_IN_MS

        def next_time() -> Milliseconds:
            return max(0, self.time_data[0].time - elapsed())

        try:
            while self._running:
                while self.time_data and not next_time():
                    self.callback(heapq.heappop(self.time_data).data)
                if self.time_data:
                    time.sleep(min(MAX_WAIT, next_time()) / 1000.0)
                else:
                    self.stop()
        finally:
            self.callback(None)


def demo() -> None:
    def time_data() -> TimeData[float]:
        import random

        t = random.uniform(0, 2)
        return TimeData(time=t, data=t)

    Sequencer([time_data() for _ in range(16)], print).run()


if __name__ == '__main__':
    demo()
