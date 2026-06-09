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
    text: str | None = None

    disable_gui: bool = False
    disable_keyboard: bool = False
    disable_sound: bool = False

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: bool = False

    model_config = ConfigDict(exclude=('_saved_text', '_sequencer'))  # ty:ignore[invalid-key]

    _sequencer: Sequencer[CharPress] | None = None
    _saved_text: str | None = None

    @cached_property
    def app(self) -> App:
        assert not self.disable_gui
        return App(self.note_labels, self.on_replay, self.text or '')

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self.on_char)

    @cached_property
    def note_labels(self) -> dict[str, NoteLabel]:
        def note_label(c: str, n: int) -> NoteLabel:
            return NoteLabel(labels=[self.player.scale.to_name(n), ' ' + c])

        return {c: note_label(c, n) for c, n in self.mapper.char_to_number.items()}

    @property
    def gui_text(self) -> str:
        return self.app.layout.get_text()

    @gui_text.setter
    def gui_text(self, text: str) -> None:
        self.app.layout.set_text(text)

    def on_char(self, c: CharPress) -> None:
        if not self.app.is_replaying and (
            self.run_in_background or self.app.focus_get()
        ):
            assert c.char
            self._on_char(c)
            if not c.is_press:
                self._on_char(CharPress(c.char.swapcase(), c.is_press))

    def _on_char(self, c: CharPress) -> None:
        if not self.disable_sound and (note := self.mapper(c.char)) is not None:
            self.player.note(note, c.is_press)
        if not self.disable_gui:
            self.app.on_char(c)

    def on_replay(self) -> None:
        self.player.stop_all()

        def on_char(c: CharPress | None) -> None:
            if c:
                self.on_char(c)
            else:
                self.app.after(0, self.on_replay)

        sequencer, self._sequencer = self._sequencer, None
        if sequencer:
            sequencer.stop()

        if self.app.is_replaying:
            self._sequencer = self.text_timings.sequencer(self.gui_text, on_char)
            self._saved_text, self.gui_text = self.gui_text, ''
            self._sequencer.start()
        elif self._saved_text is not None:
            self.gui_text, self._saved_text = self._saved_text, None

    def __call__(self):
        self.start()
        if not self.disable_gui:
            self.app.mainloop()

    def start(self) -> None:
        if not self.disable_gui:
            self.app.start()
        if not self.disable_keyboard:
            self.listener.start()
