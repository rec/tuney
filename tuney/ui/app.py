from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from tuney.audio.multi_player import MultiPlayer
from tuney.time import sequencer

from .. import time
from ..keyboard.key_press import CharPress
from ..keyboard.listener import KeyboardListener
from ..mapper.linear_mapper import LinearMapper
from .ctk_app import CTkApp, NoteLabel

type Event = time.Event[CharPress]
type Sequencer = sequencer.Sequencer[CharPress]


@dc.dataclass
class App:
    mapper: LinearMapper = LinearMapper()
    player: MultiPlayer = MultiPlayer()
    text_timings: time.TextTimings = time.TextTimings(scale=3.0)
    starting_text: str = ''
    enable_gui: bool = True
    enable_keyboard: bool = True
    enable_sound: bool = True

    _sequencer: dc.InitVar[Sequencer | None] = None
    _saved_text: dc.InitVar[str | None] = None

    @cached_property
    def ctk_app(self) -> CTkApp:
        assert self.enable_gui
        app = CTkApp(self.note_labels, self.on_replay)
        app.set_text(self.starting_text)
        return app

    @cached_property
    def listener(self) -> KeyboardListener:
        assert self.enable_keyboard
        return KeyboardListener(self.on_char)

    @cached_property
    def note_labels(self) -> dict[str, NoteLabel]:
        def note_label(c: str, n: int) -> NoteLabel:
            return NoteLabel(labels=[self.player.scale.to_name(n), ' ' + c])

        return {c: note_label(c, n) for c, n in self.mapper.char_to_number.items()}

    @property
    def text(self) -> str:
        return self.ctk_app.get_text()

    @text.setter
    def text(self, text: str) -> None:
        self.ctk_app.set_text(text)

    def on_char(self, c: CharPress) -> None:
        assert c.char
        if not self.ctk_app.is_replaying:
            self._on_char(c)
            if not c.is_press:
                self._on_char(CharPress(c.char.swapcase(), c.is_press))

    def _on_char(self, c: CharPress) -> None:
        if not self.ctk_app.is_replaying:
            if self.enable_sound and (note := self.mapper(c.char)) is not None:
                self.player.note(note, c.is_press)
            if self.enable_gui:
                self.ctk_app.on_char(c)

    def on_replay(self) -> None:
        self.player.stop_all()

        def on_char(c: CharPress | None) -> None:
            if c:
                self.on_char(c)
            else:
                self.ctk_app.after(0, self.on_replay)

        sequencer, self._sequencer = self._sequencer, None
        if sequencer:
            sequencer.stop()

        if self.ctk_app.is_replaying:
            self._sequencer = self.text_timings.sequencer(self.text, on_char)
            self._saved_text, self.text = self.text, ''
            self._sequencer.start()
        elif self._saved_text is not None:
            self.text, self._saved_text = self._saved_text, None

    def run(self):
        self.start()
        if self.enable_gui:
            self.ctk_app.mainloop()

    def start(self) -> None:
        if self.enable_gui:
            self.ctk_app.start()
        if self.enable_keyboard:
            self.listener.start()


if __name__ == '__main__':
    import sys

    text = ' '.join(sys.argv[1:])
    App().run()
