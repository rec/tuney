from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from threading import Thread
from typing import Any, Callable

from ..audio.synth_player import OscillatorController
from ..keyboard import KeyAction, KeyboardQueue
from ..mapper.linear_mapper import LinearMapper
from ..scale import twelve_tet as tt
from .controller import Controller
from .note_grid import NoteGrid, Text


@dc.dataclass
class KeyboardController(Controller):
    def key_callback(self, k: KeyAction) -> None:
        if (note_number := self.mapper(k.char)) is not None:
            self.on_note(note_number, k.is_press)

    @cached_property
    def keyboard_queue(self) -> KeyboardQueue:
        return KeyboardQueue(self.key_callback)

    def run(self) -> None:
        self.keyboard_queue.start()
        super().run()

    def stop(self) -> None:
        super().stop()
        self.keyboard_queue.stop()
        self.keyboard_queue.join()
