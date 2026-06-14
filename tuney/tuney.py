from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Annotated

import tyro
from pydantic import BaseModel, ConfigDict

from .audio.multi_player import MultiPlayer
from .keyboard.key_press import CharPress
from .keyboard.listener import KeyboardListener
from .mapper.linear_mapper import LinearMapper
from .time.sequencer import Sequencer
from .time.text_timings import TextTimings
from .ui.app import App, NoteLabel


class Tuney(BaseModel):
    # Load configs from a JSON or toml file
    config_file: Annotated[Path | None, tyro.conf.Positional] = None

    # Map letters to notes
    mapper: LinearMapper = LinearMapper()

    # How to play back audio
    player: MultiPlayer = MultiPlayer()

    # Timings for playing back texts
    text_timings: TextTimings = TextTimings(scale=3.0)

    # Text to start the program with
    text: str | list[CharPress] | None = None

    disable_gui: bool = False
    disable_sound: bool = False

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: bool = False

    model_config = ConfigDict(exclude=['_sequencer'])  # ty:ignore[invalid-key]

    _sequencer: Sequencer | None = None

    @cached_property
    def app(self) -> App:
        assert not self.disable_gui
        return App(self.note_labels, self.on_replay, self.display_text)

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self.on_char)

    @cached_property
    def note_labels(self) -> dict[str, NoteLabel]:
        def note_label(c: str, n: int) -> NoteLabel:
            return NoteLabel(labels=[self.player.scale.to_name(n), ' ' + c])

        return {c: note_label(c, n) for c, n in self.mapper.char_to_number.items()}

    @cached_property
    def char_presses(self) -> list[CharPress]:
        if self.text is None:
            return []
        if isinstance(self.text, list):
            return self.text
        else:
            return list(self.text_timings.char_presses(self.text))

    @property
    def display_text(self) -> str:
        return ''.join(c.char for c in self.char_presses)

    def on_char(self, c: CharPress) -> None:
        if self._is_listening:
            if c.char != '\b':
                self.char_presses.append(c)
            elif self.char_presses:
                self.char_presses.pop()
            self._on_char(c)
            if not c.is_press:
                # Deal with the case where the user changes the shift key status
                # while the alphabetic key is held down.
                self._on_char(CharPress(c.char.swapcase(), c.is_press))

    def _on_char(self, c: CharPress) -> None:
        if not self.disable_sound and (note := self.mapper(c.char)) is not None:
            self.player.note(note, c.is_press)
        if not self.disable_gui:
            self.app.on_char(c)

    @property
    def _is_listening(self) -> bool:
        return not self.app.is_replaying and (
            self.run_in_background or bool(self.app.focus_get())
        )

    def on_replay(self) -> None:
        self.player.stop_all()

        sequencer, self._sequencer = self._sequencer, None
        if sequencer:
            sequencer.stop()

        if self.app.is_replaying:
            self.app.layout.set_text('')
            self._sequencer = Sequencer(
                char_presses=self.char_presses, callback=self._on_replay
            )
            self._sequencer.start()
        else:
            self.app.layout.set_text(self.display_text)

    def _on_replay(self, c: CharPress | None) -> None:
        if c:
            self.on_char(c)
        else:
            self.app.after(0, self.on_replay)

    def __call__(self):
        self.start()
        if not self.disable_gui:
            self.app.mainloop()

    def start(self) -> None:
        if not self.disable_gui:
            self.app.start()
            self.listener.start()
