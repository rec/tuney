from __future__ import annotations

import json
import sys
from functools import cached_property
from pathlib import Path
from typing import Annotated

import tomlkit
import tyro
from pydantic import BaseModel, ConfigDict

from .audio.midi import MIDI
from .audio.multi_player import MultiPlayer
from .char_press import CharPress
from .keyboard.listener import KeyboardListener
from .mapper.mapper import Mapper
from .serialize import serialize
from .time.sequencer import Sequencer
from .time.text_timings import TextTimings
from .types import Milliseconds, Seconds, to_ms
from .ui.app import App, NoteLabel


class Tuney(BaseModel):
    # Load configs from a JSON or toml file
    config_file: Annotated[Path | None, tyro.conf.Positional] = None

    # Map letters to notes
    mapper: Mapper = Mapper()

    # How to play back audio
    player: MultiPlayer = MultiPlayer()

    # How to send MIDI output
    midi: MIDI = MIDI()

    # Timings for playing back texts
    text_timings: TextTimings = TextTimings(scale=3.0)

    # Text to start the program with
    text: Annotated[
        str | list[CharPress] | None,
        tyro.conf.arg(
            constructor=str,
            help_behavior_hint='(optional)',
            metavar='TEXT',
        ),
    ] = None

    # Maximum silent gap to keep in recordings, in seconds
    max_gap: float = 4.0

    cli: bool = False
    disable_sound: bool = False

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: bool = False

    model_config = ConfigDict(exclude=['_sequencer'])  # ty:ignore[invalid-key]

    _sequencer: Sequencer | None = None
    _recording_start_time: Seconds | None = None
    _recording_time_offset: Milliseconds = 0.0
    _recording_insert_time: Milliseconds | None = None
    _replay_text: str = ''

    @cached_property
    def app(self) -> App:
        assert not self.cli
        return App(self)

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
        return ''.join(c.char for c in self.char_presses if c.is_press)

    def on_char(self, c: CharPress) -> None:
        if self._is_listening:
            recorded = self.recorded_char_press(c)
            if c.is_press:
                if c.char != '\b':
                    self.char_presses.append(recorded)
                elif self.char_presses:
                    deleted_time = None
                    while self.char_presses:
                        deleted = self.char_presses.pop()
                        if deleted.is_press:
                            deleted_time = deleted.time
                            break
                    if deleted_time is not None:
                        self._recording_insert_time = deleted_time
                self.app.layout.set_text(self.display_text)
            else:
                if c.char != '\b':
                    self.char_presses.append(recorded)
                # Deal with the case where the user changes the shift key status
                # while the alphabetic key is held down.
                self._on_char(CharPress(c.char.swapcase(), False))
            self._on_char(c)

    def recorded_char_press(self, c: CharPress) -> CharPress:
        if self._recording_start_time is None and c.is_press:
            self._recording_start_time = c.time
        start = self._recording_start_time or c.time
        raw_time = to_ms(c.time - start)
        if self._recording_insert_time is not None and c.is_press and c.char != '\b':
            self._recording_time_offset = self._recording_insert_time - raw_time
            self._recording_insert_time = None
        recorded_time = raw_time + self._recording_time_offset
        max_gap = to_ms(self.max_gap)
        if max_gap > 0 and c.is_press and not self._recorded_notes_on():
            time = self.char_presses[-1].time if self.char_presses else 0
            gap = recorded_time - time
            if gap > max_gap:
                self._recording_time_offset -= gap - max_gap
                recorded_time = raw_time + self._recording_time_offset
        return CharPress(c.char, c.is_press, recorded_time)

    def _recorded_notes_on(self) -> set[str]:
        result = set()
        for c in self.char_presses:
            if c.is_press:
                result.add(c.char)
            else:
                result.discard(c.char)
        return result

    def clear(self) -> None:
        self.char_presses.clear()
        self._recording_start_time = None
        self._recording_time_offset = 0.0
        self._recording_insert_time = None
        self._replay_text = ''
        if not self.cli:
            self.app.layout.set_text('')

    def save(self, path: Path) -> None:
        data = serialize(self.dump_data())
        match path.suffix:
            case '.toml':
                text = tomlkit.dumps(data)
            case '.json':
                text = json.dumps(data, indent=2) + '\n'
            case _:
                raise ValueError(f'Do not understand file {path}')
        path.write_text(text)

    def dump_data(self) -> dict[str, object]:
        data = self.model_dump()
        if self.char_presses:
            data['text'] = [c.model_dump() for c in self.char_presses]
        return data

    def _on_char(self, c: CharPress) -> None:
        if (note := self.mapper(c.char)) is not None:
            if not self.disable_sound:
                self.player.on_note(note, c.is_press)
            self.midi(note, c.is_press)
        if not self.cli:
            self.app.on_char(c)

    @property
    def _is_listening(self) -> bool:
        return (
            not self.app.is_replaying
            and not self.app.is_saving
            and (self.run_in_background or self.app.has_focus)
        )

    def on_replay(self) -> None:
        self.player.stop_all()

        sequencer, self._sequencer = self._sequencer, None
        if sequencer:
            sequencer.stop()

        if self.app.is_replaying:
            self._replay_text = ''
            self.app.layout.set_text(self._replay_text)
            self._sequencer = Sequencer(
                char_presses=self.char_presses, callback=self._on_replay
            )
            self._sequencer.start()
        else:
            self._replay_text = ''
            self.app.layout.set_text(self.display_text)

    def _on_replay(self, c: CharPress | None) -> None:
        if c:
            if c.is_press:
                self._replay_text += c.char
                self.app.after(0, self.app.layout.set_text, self._replay_text)
            self._on_char(c)
        elif self.app.is_replaying and self._sequencer is not None:
            self.app.after(0, self._finish_replay)

    def _finish_replay(self) -> None:
        self.app.is_replaying = False

    def __call__(self) -> None:
        if self.cli:
            self._run_cli()
        else:
            self.start()
            self.app.mainloop()

    def start(self) -> None:
        self.app.start()
        self.listener.start()

    def _run_cli(self) -> None:
        if not self.char_presses:
            sys.exit('CLI mode requires text to play')
        if self.disable_sound:
            sys.exit('CLI mode requires sound')

        def callback(c: CharPress | None) -> None:
            if c:
                self._on_char(c)

        try:
            Sequencer(char_presses=self.char_presses, callback=callback).run()
        finally:
            self.player.stop_all()
            self.player.wait()
            self.player.close()
