from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from pynput.keyboard import Key

from ..audio.synth_player import OscillatorController
from ..keyboard.listener import KeyboardListener, KeyPress
from ..mapper.linear_mapper import LinearMapper
from ..scale import twelve_tet
from ..scale.scale import Scale
from .grid import NoteGrid, NoteLabel

assert isinstance(twelve_tet, Scale)

KEYS = {Key.space: ' ', Key.enter: '\n', Key.backspace: '\b'}


@dc.dataclass
class Controller:
    mapper: LinearMapper = LinearMapper()
    osc: OscillatorController = OscillatorController()
    scale: Scale = twelve_tet
    use_gui: bool = True
    starting_text: str = ''

    @cached_property
    def grid(self) -> NoteGrid:
        return NoteGrid(self.texts)

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self.on_key)

    @cached_property
    def texts(self) -> dict[str, NoteLabel]:
        items = self.mapper.char_to_number.items()
        return {c: NoteLabel((self.scale.to_name(n), ' ' + c)) for c, n in items}

    def on_key(self, k: KeyPress) -> None:
        if char := getattr(k.key, 'char', None) or KEYS.get(k.key):
            if (note := self.mapper(char)) is not None:
                self.play_note(char, note, k.is_press)
            else:
                self.grid.on_char(char, k.is_press)

    def play_note(self, char: str, note_number: int, is_press: bool) -> None:
        self.osc.note(note_number, is_press)
        self.grid.on_char(char, is_press)

    def run(self) -> None:
        self.grid.start()
        self.listener.start()
        self.grid.mainloop()


if __name__ == '__main__':
    print('start')
    Controller().run()
    print('done')
