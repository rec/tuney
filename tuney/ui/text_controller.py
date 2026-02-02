from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from threading import Thread
from typing import TypeAlias

from ..keyboard import KeyAction
from ..time import event
from ..time.text_timings import TextTimings
from .controller import Controller

Event: TypeAlias = event.Event[KeyAction]
Runner: TypeAlias = event.Runner[KeyAction]


@dc.dataclass
class TextController(Controller):
    text: str = ''
    timings: TextTimings = dc.field(default_factory=TextTimings)

    @cached_property
    def runner(self) -> Runner:
        events = []
        for char, begin, end in self.timings(self.text):
            events.append(Event(begin, KeyAction(char, True)))
            events.append(Event(end, KeyAction(char, False)))

        return event.Runner(events, self.key_callback)

    def run(self) -> None:
        Thread(target=self.runner.run).start()
        super().run()

    def stop(self) -> None:
        super().stop()
        self.runner.stop()


def main() -> None:
    # msg = "Now is the time for all good men to come to the aid of the party"
    msg = 'Now is the time'
    with TextController(text=msg):
        pass


if __name__ == '__main__':
    main()
