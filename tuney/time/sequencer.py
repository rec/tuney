from __future__ import annotations

import time
from collections.abc import Callable
from itertools import pairwise
from typing import Annotated, Any, override

from pydantic import AfterValidator, BaseModel

from ..keyboard.char_press import CharPress
from ..runnable import Runnable
from . import Milliseconds, Seconds, to_ms, to_seconds

MAX_WAIT_MS: Milliseconds = 100.0


def is_sorted(presses: list[CharPress]) -> list[CharPress]:
    if any(i > j for i, j in pairwise(presses)):
        raise ValueError('char_presses are not sorted by time')
    return presses


class Sequencer(BaseModel, Runnable, frozen=True):
    char_presses: Annotated[list[CharPress], AfterValidator(is_sorted)]
    callback: Callable[[CharPress | None], Any]

    @override
    def _run(self) -> None:
        try:
            start: Seconds = time.time()
            for cp in self.char_presses:
                while True:
                    if not self._running:
                        return
                    elapsed_ms = to_ms(time.time() - start)
                    if (next_time := max(0, cp.time - elapsed_ms)) <= 0:
                        self.callback(cp)
                        break
                    time.sleep(to_seconds(min(MAX_WAIT_MS, next_time)))
        finally:
            self.callback(None)


def demo() -> None:
    def char_press() -> CharPress:
        import random

        t = random.uniform(0, 2)
        return CharPress(char=str(t), time=t)

    Sequencer(char_presses=[char_press() for _ in range(16)], callback=print).run()


if __name__ == '__main__':
    demo()
