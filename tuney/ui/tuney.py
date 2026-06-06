from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Annotated

import tyro
from pydantic import BaseModel, ConfigDict

from tuney.audio.multi_player import MultiPlayer
from tuney.time.sequencer import Sequencer

from .. import time
from ..keyboard.key_press import CharPress
from ..keyboard.listener import KeyboardListener
from ..mapper.linear_mapper import LinearMapper
from .app import App, NoteLabel


class Tuney(BaseModel):
    # Load configs from a JSON or toml file
    config_file: Annotated[Path | None, tyro.conf.Positional] = None

    # Map letters to notes
    mapper: LinearMapper = LinearMapper()

    # How to play back audio
    player: MultiPlayer = MultiPlayer()

    # Timings for playing back texts
    text_timings: time.TextTimings = time.TextTimings(scale=3.0)

    # Text to start the program with
    text: str = ''

    disable_gui: bool = False
    disable_keyboard: bool = False
    disable_sound: bool = False

    model_config = ConfigDict(exclude=('_saved_text', '_sequencer'))  # ty:ignore[invalid-key]

    _sequencer: Annotated[Sequencer[CharPress] | None, tyro.conf.Suppress] = None
    _saved_text: Annotated[str | None, tyro.conf.Suppress] = None

    @cached_property
    def gui_app(self) -> App:
        assert not self.disable_gui
        app = App(self.note_labels, self.on_replay)
        app.set_text(self.text)
        return app

    @cached_property
    def listener(self) -> KeyboardListener:
        assert not self.disable_keyboard
        return KeyboardListener(self.on_char)

    @cached_property
    def note_labels(self) -> dict[str, NoteLabel]:
        def note_label(c: str, n: int) -> NoteLabel:
            return NoteLabel(labels=[self.player.scale.to_name(n), ' ' + c])

        return {c: note_label(c, n) for c, n in self.mapper.char_to_number.items()}

    @property
    def gui_text(self) -> str:
        return self.gui_app.get_text()

    @gui_text.setter
    def gui_text(self, text: str) -> None:
        self.gui_app.set_text(text)

    def on_char(self, c: CharPress) -> None:
        assert c.char
        if not self.gui_app.is_replaying:
            self._on_char(c)
            if not c.is_press:
                self._on_char(CharPress(c.char.swapcase(), c.is_press))

    def _on_char(self, c: CharPress) -> None:
        if not self.gui_app.is_replaying:
            if not self.disable_sound and (note := self.mapper(c.char)) is not None:
                self.player.note(note, c.is_press)
            if not self.disable_gui:
                self.gui_app.on_char(c)

    def on_replay(self) -> None:
        self.player.stop_all()

        def on_char(c: CharPress | None) -> None:
            if c:
                self.on_char(c)
            else:
                self.gui_app.after(0, self.on_replay)

        sequencer, self._sequencer = self._sequencer, None
        if sequencer:
            sequencer.stop()

        if self.gui_app.is_replaying:
            self._sequencer = self.text_timings.sequencer(self.gui_text, on_char)
            self._saved_text, self.gui_text = self.gui_text, ''
            self._sequencer.start()
        elif self._saved_text is not None:
            self.gui_text, self._saved_text = self._saved_text, None

    def __call__(self):
        self.start()
        if not self.disable_gui:
            self.gui_app.mainloop()

    def start(self) -> None:
        if not self.disable_gui:
            self.gui_app.start()
        if not self.disable_keyboard:
            self.listener.start()
