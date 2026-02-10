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
    use_keyboard: bool = True
    use_osc: bool = True
    starting_text: str = ''
    in_playback: bool = False

    @cached_property
    def grid(self) -> NoteGrid:
        assert self.use_gui
        return NoteGrid(self.note_labels, self.starting_text)

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self.on_key)

    @cached_property
    def note_labels(self) -> dict[str, NoteLabel]:
        items = self.mapper.char_to_number.items()
        return {c: NoteLabel((self.scale.to_name(n), ' ' + c)) for c, n in items}

    def on_key(self, k: KeyPress) -> None:
        if char := getattr(k.key, 'char', '') or KEYS.get(k.key, ''):
            self.on_char(char, k.is_press)

    def on_char(self, char: str, is_press: bool) -> None:
        if self.use_osc and (note := self.mapper(char)) is not None:
            self.osc.note(note, is_press)
        if self.use_gui:
            self.grid.on_char(char, is_press)

    def run(self) -> None:
        if self.use_gui:
            self.grid.start()

        if self.use_keyboard:
            self.listener.start()

        if self.use_gui:
            self.grid.mainloop()


if __name__ == '__main__':
    print('start')
    Controller().run()
    print('done')
