from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Protocol, cast

from ..audio.player import Player
from ..config.text_file import read_text_file
from ..config.tuney import Tuney
from ..keyboard.listener import KeyboardListener
from ..midi.listener import MidiListener
from ..presets.autosave import Autosave
from ..time.char_press import CharPress
from ..ui import startup
from .audio_recorder import AudioRecorder
from .global_config import GlobalConfig
from .key_recorder import KeyRecorder
from .platform_info import report_error
from .text_timing import text_timing_rows

if TYPE_CHECKING:
    from ..ui.main_window import MainWindow
    from .app import App


class _AppRuntime(Protocol):
    def on_char(self, c: CharPress) -> None: ...

    def play_note(self, note: int, is_press: bool) -> None: ...


class AppMembers(Tuney):
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    @cached_property
    def main_window(self) -> MainWindow:
        assert self.gui
        from ..ui.main_window import MainWindow

        return MainWindow(cast('App', self))

    @cached_property
    def keyboard_listener(self) -> KeyboardListener:
        runtime = cast(_AppRuntime, self)
        return KeyboardListener(
            self.main_window.on_key if self.gui else lambda c: runtime.on_char(c)
        )

    @cached_property
    def midi_listener(self) -> MidiListener:
        runtime = cast(_AppRuntime, self)
        return self.midi.listener(
            lambda note, is_press: runtime.play_note(note, is_press)
        )

    @cached_property
    def player(self) -> Player:
        return Player(
            device=self.device,
            sound=self.sound,
            scale=self.scale,
            tuning=self.tuning,
            buffer_size=self.global_config.buffer_size,
            increase_buffer_size=self.global_config.increase_buffer_size,
        )

    @cached_property
    def global_config(self) -> GlobalConfig:
        return GlobalConfig.read()

    @cached_property
    def note_labels(self) -> dict[str, str]:
        return {
            c: '\n'.join([self.scale.to_name(n), ' ' + c])
            for c, n in self.mapper.char_to_number.items()
        }

    @cached_property
    def key_recorder(self) -> KeyRecorder:
        return KeyRecorder()

    @cached_property
    def audio_recorder(self) -> AudioRecorder:
        return AudioRecorder()

    @cached_property
    def char_presses(self) -> list[CharPress]:
        if self.text_file is not None:
            try:
                return list(
                    self.text_timings.char_presses(read_text_file(self.text_file))
                )
            except Exception as e:
                report_error(str(e))
        if self.text is None:
            return []
        if isinstance(self.text, list):
            return self.text
        return list(self.text_timings.char_presses(self.text))

    @property
    def display_text(self) -> str:
        return ''.join(c.char for c in self.char_presses if c.is_press)

    @property
    def display_text_timings(self) -> list[list[str]]:
        return text_timing_rows(self.char_presses)

    @cached_property
    def _autosave(self) -> Autosave:
        return Autosave(file=startup.autosave_file)

    @property
    def _is_listening(self) -> bool:
        return (
            not self.main_window.is_replaying
            and not self.main_window.is_saving
            and not self.main_window.focus_in_control_panel
            and (self.run_in_background or self.main_window.has_focus)
        )
