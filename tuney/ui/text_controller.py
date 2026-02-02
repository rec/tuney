from __future__ import annotations

import dataclasses as dc
from collections.abc import Callable
from functools import cached_property
from threading import Thread
from typing import Any, TypeAlias

from ..audio.synth_player import OscillatorController
from ..keyboard import KeyAction, KeyboardQueue
from ..mapper.linear_mapper import LinearMapper
from ..scale import twelve_tet as tt
from ..time import event
from ..time.text_timings import TextTimings
from .controller import Controller
from .note_grid import NoteGrid, Text

Event: TypeAlias = event.Event[KeyAction]
Runner: TypeAlias = event.Runner[KeyAction]


@dc.dataclass
class TextController(Controller):
    text: str = ""
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
    import time

    # msg = "Now is the time for all good men to come to the aid of the party"
    msg = "Now is the time"
    with TextController(text=msg) as tc:
        pass


if __name__ == "__main__":
    main()
