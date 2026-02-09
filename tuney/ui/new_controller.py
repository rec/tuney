from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from ..audio.synth_player import OscillatorController
from ..keyboard.simple_listener import KeyboardListener, KeyPress
from ..mapper.linear_mapper import LinearMapper
from ..scale import twelve_tet
from ..scale.scale import Scale
from . import Text
from .grid import NoteGrid

assert isinstance(twelve_tet, Scale)


@dc.dataclass
class Controller:
    mapper: LinearMapper = LinearMapper()
    osc: OscillatorController = OscillatorController()
    scale: Scale = twelve_tet

    @cached_property
    def grid(self) -> NoteGrid:
        return NoteGrid(self.texts, update_entries=True)

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self._on_key)

    @cached_property
    def texts(self) -> dict[str, Text]:
        items = self.mapper.char_to_number.items()
        return {c: Text((twelve_tet.to_name(n), ' ' + c)) for c, n in items}

    def _on_key(self, k: KeyPress) -> None:
        if (c := getattr(k.key, 'char', '')) and (note := self.mapper(c)) is not None:
            self.on_note(c, note, k.is_press)
        self.grid.on_key(k)

    def on_note(self, char: str, note_number: int, is_press: bool) -> None:
        if not self.osc.note(note_number, is_press):
            pass
        self.grid.on_char(char, is_press)

    def run(self) -> None:
        self.grid.start()
