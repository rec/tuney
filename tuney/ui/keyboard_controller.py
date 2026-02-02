from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from ..keyboard import KeyboardQueue
from .controller import Controller


@dc.dataclass
class KeyboardController(Controller):
    @cached_property
    def keyboard_queue(self) -> KeyboardQueue:
        return KeyboardQueue(self.key_callback)

    def run(self) -> None:
        self.keyboard_queue.start()
        super().run()

    def stop(self) -> None:
        super().stop()
        self.keyboard_queue.stop()

    def join(self) -> None:
        self.keyboard_queue.join()
