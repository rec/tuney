from __future__ import annotations

import time
from collections.abc import Callable
from itertools import pairwise
from threading import Event
from typing import Annotated, override

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from ..app.runnable import Runnable
from .char_press import CharPress
from .units import Milliseconds, Seconds, to_ms, to_seconds

MAX_WAIT_MS: Milliseconds = 100.0


def is_sorted(presses: list[CharPress]) -> list[CharPress]:
    if any(i > j for i, j in pairwise(presses)):
        raise ValueError('char_presses are not sorted by time')
    return presses


class Sequencer(BaseModel, Runnable, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    char_presses: Annotated[list[CharPress], AfterValidator(is_sorted)]
    callback: Callable[[CharPress | None], object]
    stop_event: Event = Field(default_factory=Event, exclude=True)

    @override
    def _run(self) -> None:
        try:
            self.stop_event.clear()
            start: Seconds = time.time()
            for cp in self.char_presses:
                while True:
                    if not self._running:
                        return
                    elapsed_ms = to_ms(time.time() - start)
                    if (next_time := max(0, cp.time - elapsed_ms)) <= 0:
                        self.callback(cp)
                        break
                    if self.stop_event.wait(to_seconds(min(MAX_WAIT_MS, next_time))):
                        return
        finally:
            self.callback(None)

    @override
    def stop(self) -> None:
        self.stop_event.set()
        super().stop()


def demo() -> None:
    def char_press() -> CharPress:
        import random

        t = random.uniform(0, 2)
        return CharPress(char=str(t), time=t)

    Sequencer(char_presses=[char_press() for _ in range(16)], callback=print).run()


if __name__ == '__main__':
    demo()
