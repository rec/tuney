from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, override

from pydantic import BaseModel

from ..runnable import Runnable
from ..types import Milliseconds, Seconds, to_ms, to_seconds
from .time_data import TimeData

MAX_WAIT_MS: Milliseconds = 100.0


class Sequencer[Data](BaseModel, Runnable, frozen=True):
    time_data: list[TimeData]
    callback: Callable[[Data | None], Any]

    @override
    def _run(self) -> None:
        try:
            start: Seconds = time.time()
            for td in self.time_data:
                while True:
                    if not self._running:
                        return
                    elapsed_ms = to_ms(time.time() - start)
                    if (next_time := max(0, td.time - elapsed_ms)) <= 0:
                        self.callback(td.data)
                        break
                    time.sleep(to_seconds(min(MAX_WAIT_MS, next_time)))
        finally:
            self.callback(None)


def demo() -> None:
    def time_data() -> TimeData[float]:
        import random

        t = random.uniform(0, 2)
        return TimeData(time=t, data=t)

    Sequencer(time_data=[time_data() for _ in range(16)], callback=print).run()


if __name__ == '__main__':
    demo()
