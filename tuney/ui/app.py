from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from pathlib import Path
from typing import Annotated

import tyro

from tuney.audio.multi_player import MultiPlayer
from tuney.time.sequencer import Sequencer

from .. import time
from ..keyboard.key_press import CharPress
from ..keyboard.listener import KeyboardListener
from ..mapper.linear_mapper import LinearMapper
from .ctk_app import CTkApp, NoteLabel

type Event = time.Event[CharPress]


@dc.dataclass
class App:
    # Map letters to notes
    mapper: LinearMapper = LinearMapper()

    # How to play back audio
    player: MultiPlayer = MultiPlayer()

    # Timings for playing back texts
    text_timings: time.TextTimings = time.TextTimings(scale=3.0)

    # Text to start the program with
    starting_text: str = ''

    disable_gui: bool = False
    disable_keyboard: bool = False
    disable_sound: bool = False

    # Load configs from a JSON or toml file
    config_file: Annotated[
        Path | None,
        tyro.conf.Positional,
    ] = None

    _sequencer: Annotated[
        dc.InitVar[Sequencer[CharPress] | None],
        tyro.conf.Suppress,
    ] = None

    _saved_text: Annotated[
        dc.InitVar[str | None],
        tyro.conf.Suppress,
    ] = None

    @cached_property
    def ctk_app(self) -> CTkApp:
        assert not self.disable_gui
        app = CTkApp(self.note_labels, self.on_replay)
        app.set_text(self.starting_text)
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
            if not self.disable_sound and (note := self.mapper(c.char)) is not None:
                self.player.note(note, c.is_press)
            if not self.disable_gui:
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

    def __call__(self):
        self.start()
        if not self.disable_gui:
            self.ctk_app.mainloop()

    def start(self) -> None:
        if not self.disable_gui:
            self.ctk_app.start()
        if not self.disable_keyboard:
            self.listener.start()
