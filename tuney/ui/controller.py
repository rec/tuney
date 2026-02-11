from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from pynput.keyboard import Key

from ..audio.synth_player import OscillatorController
from ..keyboard.listener import KeyboardListener, KeyPress
from ..mapper.linear_mapper import LinearMapper
from ..scale import twelve_tet
from ..scale.scale import Scale
from ..time.text_timings import TextTimings
from .ctk_app import CTkApp, NoteLabel

KEYS = {Key.space: ' ', Key.enter: '\n', Key.backspace: '\b'}


@dc.dataclass
class Controller:
    mapper: LinearMapper = LinearMapper()
    osc: OscillatorController = OscillatorController()
    scale_name: str = 'twelve_tet'
    text_timings: TextTimings = TextTimings()
    starting_text: str = ''
    use_gui: bool = True
    use_keyboard: bool = True
    use_osc: bool = True

    _replay: dc.InitVar[bool] = False

    @cached_property
    def ctk_app(self) -> CTkApp:
        assert self.use_gui
        return CTkApp(self.note_labels, self.starting_text, self.on_replay)

    @cached_property
    def listener(self) -> KeyboardListener:
        assert self.use_keyboard
        return KeyboardListener(self.on_key)

    @cached_property
    def note_labels(self) -> dict[str, NoteLabel]:
        items = self.mapper.char_to_number.items()
        return {c: NoteLabel((self.scale.to_name(n), ' ' + c)) for c, n in items}

    @cached_property
    def scale(self) -> Scale:
        assert isinstance(twelve_tet, Scale)
        return twelve_tet  # TODO

    def on_key(self, k: KeyPress) -> None:
        if c := getattr(k.key, 'char', '') or KEYS.get(k.key, ''):
            self.on_char(c, k.is_press)

    def on_char(self, char: str, is_press: bool = True) -> None:
        if not self._replay:
            if self.use_osc and (note := self.mapper(char)) is not None:
                self.osc.note(note, is_press)
            if self.use_gui:
                self.ctk_app.on_char(char, is_press)

    def on_replay(self) -> None:
        self._replay = not self._replay
        if self._replay:
            self.text_timings.make_runner(self.ctk_app.text, self.on_char).run()

    def start(self) -> None:
        if self.use_gui:
            self.ctk_app.start()
        if self.use_keyboard:
            self.listener.start()

    def run(self):
        self.start()
        if self.use_gui:
            self.ctk_app.mainloop()


if __name__ == '__main__':
    import sys

    text = ' '.join(sys.argv[1:])
    Controller().run()
