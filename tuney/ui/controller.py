from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from threading import Thread
from typing import Any, Callable

from ..audio.synth_player import OscillatorController
from ..keyboard import KeyAction, KeyboardQueue
from ..mapper.linear_mapper import LinearMapper
from ..scale import twelve_tet as tt
from .note_grid import NoteGrid, Text


@dc.dataclass
class Controller:
    mapper: LinearMapper = LinearMapper()
    oc: OscillatorController = OscillatorController()

    @cached_property
    def grid(self) -> NoteGrid:
        items = self.mapper.char_to_number.items()
        texts = {n: Text((tt.number_to_name(n), " " + c)) for c, n in items}
        return NoteGrid(list(texts.values()))

    def key_callback(self, k: KeyAction) -> None:
        if (note_number := self.mapper(k.char)) is not None:
            self.on_note(note_number, k.is_press)

    def on_note(self, note_number: int, is_press: bool) -> None:
        if self.oc.note(note_number, is_press) and False:
            self.grid.texts[note_number].on = is_press
            self.grid.redraw()

    def run(self) -> None:
        self.grid.run()

    def stop(self) -> None:
        self.grid.stop()

    def __enter__(self) -> Controller:
        self.run()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
