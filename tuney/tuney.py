from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import tomlkit
import tyro
from pydantic import BaseModel, Field, field_validator

from .audio.midi import MIDI
from .audio.mixer import NotePress
from .audio.multi_player import MultiPlayer
from .autosave import Autosave
from .control import control
from .keyboard.char_press import CharPress
from .keyboard.listener import KeyboardListener
from .mapper.mapper import Mapper
from .presets import merged_data, read_preset
from .recorders import AudioRecorder, KeyRecorder
from .serialize import serialize
from .time import to_ms
from .time.sequencer import Sequencer
from .time.text_timings import TextTimings

if TYPE_CHECKING:
    from .ui.app import App


class NoteLabel(BaseModel, frozen=True):
    labels: list[str]
    on: bool = False

    @cached_property
    def text(self) -> str:
        return '\n'.join(self.labels)


class Tuney(BaseModel):
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    # Named performance preset to load
    preset: Annotated[
        str | None, tyro.conf.arg(aliases=['-p']), control(general=True, beginner=True)
    ] = None

    # Load configs from a JSON or toml file
    config_file: Annotated[
        Path | None, tyro.conf.arg(aliases=['-c']), control(hidden=True)
    ] = None

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
            aliases=['-t'],
            constructor=str,
            help_behavior_hint='(optional)',
            metavar='TEXT',
        ),
        control(hidden=True),
    ] = None

    # Positional text to start the program with
    text_args: Annotated[
        list[str],
        tyro.conf.Positional,
        tyro.conf.arg(name='text', metavar='TEXT'),
        control(hidden=True),
    ] = Field(default_factory=list, exclude=True)

    # Maximum silent gap to keep in recordings, in seconds
    max_gap: Annotated[
        float, tyro.conf.arg(aliases=['-m']), control(general=True, beginner=True)
    ] = 4.0

    # Time to hover over a widget before showing help, in seconds
    hover_time: Annotated[float, control(general=True)] = 1.0

    # Time to hold backspace before it starts repeating, in seconds
    backspace_repeat_delay: Annotated[float, control(hidden=True)] = 2.0

    # Backspace repeats per second after backspace_repeat_delay
    backspace_repeat_rate: Annotated[float, control(hidden=True)] = 4.0

    # Open the graphical interface
    gui: Annotated[bool, tyro.conf.arg(aliases=['-g']), control(hidden=True)] = False

    # Disable synthesized audio output
    silent: Annotated[
        bool, tyro.conf.arg(aliases=['-s']), control(general=True, beginner=True)
    ] = False

    # Audio file to write while playing text
    output: Annotated[
        Path | None, tyro.conf.arg(aliases=['-o']), control(hidden=True)
    ] = None

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: Annotated[
        bool, tyro.conf.arg(aliases=['-b']), control(general=True)
    ] = False

    # Path to the automatically saved GUI state
    autosave_file: tyro.conf.Suppress[Path | None] = Field(default=None, exclude=True)

    @field_validator('text')
    @classmethod
    def _validate_text(
        cls, value: str | list[CharPress] | None
    ) -> str | list[CharPress] | None:
        if isinstance(value, list):
            Sequencer(char_presses=value, callback=lambda _: None)
        return value

    def model_post_init(self, __context: object) -> None:
        if self.text_args:
            object.__setattr__(self, 'text', ' '.join(self.text_args))
            self.__dict__.pop('char_presses', None)
        if self.output:
            object.__setattr__(self, 'gui', False)

    @cached_property
    def app(self) -> App:
        assert self.gui
        from .ui.app import App

        return App(self)

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self.app.on_key if self.gui else self.on_char)

    @cached_property
    def note_labels(self) -> dict[str, NoteLabel]:
        def note_label(c: str, n: int) -> NoteLabel:
            return NoteLabel(labels=[self.player.scale.to_name(n), ' ' + c])

        return {c: note_label(c, n) for c, n in self.mapper.char_to_number.items()}

    @cached_property
    def key_recorder(self) -> KeyRecorder:
        return KeyRecorder()

    @cached_property
    def audio_recorder(self) -> AudioRecorder:
        return AudioRecorder()

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
        if c.char == '\b' and not c.is_press:
            self._stop_backspace_repeat()
        if self._is_listening:
            if c.char != '\b' or (c.is_press and self.char_presses):
                self.app.record_undo()
            recorded = self.key_recorder.recorded_char_press(
                c, self.char_presses, self.max_gap
            )
            if c.is_press:
                if c.char != '\b':
                    self.append_char_press(recorded)
                elif self.char_presses:
                    self.key_recorder.delete_last_char(self.char_presses)
                    self._start_backspace_repeat()
                self.app.ui.set_text(self.display_text)
            else:
                if c.char != '\b':
                    self.append_char_press(recorded)
                # Deal with the case where the user changes the shift key status
                # while the alphabetic key is held down.
                self._on_char(CharPress(c.char.swapcase(), False))
            self._on_char(c)

    def append_char_press(self, c: CharPress) -> None:
        self.char_presses.append(c)
        if len(self.char_presses) > 1 and c < (d := self.char_presses[-2]):
            print(f'Out-of-order char_press: {c} follows {d}', file=sys.stderr)
            self.char_presses.sort()

    def _start_backspace_repeat(self) -> None:
        self._stop_backspace_repeat()
        if self.backspace_repeat_delay >= 0 and self.backspace_repeat_rate > 0:
            self.key_recorder.backspace_repeat_after_id = self.app.after(
                round(to_ms(self.backspace_repeat_delay)),
                self._repeat_backspace,
            )

    def _repeat_backspace(self) -> None:
        self.key_recorder.backspace_repeat_after_id = None
        if not self._is_listening or not self.char_presses:
            return
        self.app.record_undo()
        self.key_recorder.delete_last_char(self.char_presses)
        self.app.ui.set_text(self.display_text)
        self._on_char(CharPress('\b', time=0))
        if self.char_presses:
            self.key_recorder.backspace_repeat_after_id = self.app.after(
                round(1000 / self.backspace_repeat_rate),
                self._repeat_backspace,
            )

    def _stop_backspace_repeat(self) -> None:
        if self.key_recorder.backspace_repeat_after_id is not None:
            self.app.after_cancel(self.key_recorder.backspace_repeat_after_id)
            self.key_recorder.backspace_repeat_after_id = None

    def clear(self) -> None:
        if self.gui and self.char_presses:
            self.app.record_undo()
        self.char_presses.clear()
        self.key_recorder.clear()
        if self.gui:
            self.app.ui.set_text('')

    def randomize_timing(self) -> None:
        text = self.display_text
        if not text:
            return
        if self.gui:
            self.app.record_undo()
        self.__dict__['char_presses'] = list(self.text_timings.char_presses(text))
        self.key_recorder.clear()
        if self.gui:
            self.app.ui.set_text(text)

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

    @cached_property
    def _autosave(self) -> Autosave:
        return Autosave(file=self.autosave_file)

    def apply_preset(self, name: str) -> None:
        char_presses = self.__dict__.get('char_presses')
        data = merged_data(self.model_dump(), read_preset(name), {'preset': name})
        validated = type(self).model_validate(data)
        for field in type(self).model_fields:
            object.__setattr__(self, field, getattr(validated, field))
        self._clear_cached_values()
        if char_presses is not None:
            self.__dict__['char_presses'] = char_presses

    def restore_data(self, data: dict[str, object]) -> None:
        autosave_file = self.autosave_file
        validated = type(self).model_validate(data)
        for field in type(self).model_fields:
            object.__setattr__(self, field, getattr(validated, field))
        if 'autosave_file' not in data:
            object.__setattr__(self, 'autosave_file', autosave_file)
        self._clear_cached_values()

    def dump_data(self) -> dict[str, object]:
        data = self.model_dump()
        if self.char_presses:
            data['text'] = [c.model_dump() for c in self.char_presses]
        return data

    def _on_char(self, c: CharPress) -> None:
        if (note := self.mapper(c.char)) is not None:
            if not self.silent:
                self.player.on_note(note, c.is_press)
            self.midi(note, c.is_press)
        if self.gui:
            self.app.on_char(c)

    def _clear_cached_values(self) -> None:
        fields = Tuney.model_fields
        keep = {'app', 'listener', 'key_recorder', 'audio_recorder'}
        for key in tuple(self.__dict__):
            if key not in fields and key not in keep:
                self.__dict__.pop(key, None)

    @property
    def _is_listening(self) -> bool:
        return (
            not self.app.is_replaying
            and not self.app.is_saving
            and not self.app.focus_in_control_panel
            and (self.run_in_background or self.app.has_focus)
        )

    def on_replay(self) -> None:
        self.key_recorder.on_replay(self)

    def _replay_char_presses(self) -> list[CharPress]:
        char_presses = _loop_window(
            self._replay_source_char_presses(),
            self.app.loop_before * 1000,
            self.app.loop_after * 1000,
        )
        if self.app.loop_tempo == 1:
            return char_presses
        return [
            CharPress(c.char, c.is_press, time=c.time / self.app.loop_tempo)
            for c in char_presses
        ]

    def _replay_source_char_presses(self) -> list[CharPress]:
        if self.app.loop_replay and self.app.randomize_on_each_loop:
            return list(self.text_timings.char_presses(self.display_text))
        return self.char_presses

    def _stop_replaying(self) -> None:
        self.app.is_replaying = False

    def __call__(self) -> None:
        if self.gui:
            self._autosave.restore_if(self)
            self.start()
            self.app.mainloop()
        else:
            self._run_cli()

    def start(self) -> None:
        self.app.start()
        if self.run_in_background:
            self.listener.start()

    def _run_cli(self) -> None:
        if not self.char_presses:
            _exit_with_missing_text()
        if self.silent and not self.output:
            sys.exit('CLI mode requires sound')

        completed = False
        start_time = datetime.now(timezone.utc)

        def comment() -> str:
            return tomlkit.dumps(
                {
                    'original_text': self.display_text,
                    'recording_start_time': start_time.isoformat(),
                    'recording_finish_time': datetime.now(timezone.utc).isoformat(),
                    'settings': tomlkit.dumps(serialize(self.dump_data())),
                }
            )

        try:
            if self.output and self.silent:
                self.player.render_file(self.output, self._note_events(), comment)
            else:
                if self.output:
                    self.player.start_recording(self.output, comment)
                self._play_cli()
            completed = True
        finally:
            if not self.silent:
                self.player.stop_all()
                self.player.wait()
                if self.output:
                    self.player.stop_recording()
                self.player.close()
            if self.output and not completed:
                self.output.unlink(missing_ok=True)

    def _note_events(self) -> list[tuple[int, NotePress]]:
        events: list[tuple[int, NotePress]] = []
        for press in self.char_presses:
            if (note := self.mapper(press.char)) is not None:
                frame = round(press.time * self.player.sample_rate / 1000)
                events.append((frame, NotePress(note, press.is_press)))
        return events

    def _output_comment(self) -> Callable[[], str]:
        start_time = datetime.now(timezone.utc)

        def comment() -> str:
            return tomlkit.dumps(
                {
                    'original_text': self.display_text,
                    'recording_start_time': start_time.isoformat(),
                    'recording_finish_time': datetime.now(timezone.utc).isoformat(),
                    'settings': tomlkit.dumps(serialize(self.dump_data())),
                }
            )

        return comment

    def _play_cli(self) -> None:
        def callback(c: CharPress | None) -> None:
            if c:
                if c.is_press:
                    print(c.char, end='', flush=True)
                self._on_char(c)

        try:
            Sequencer(char_presses=self.char_presses, callback=callback).run()
        except KeyboardInterrupt:
            print()
            raise
        print()


def _loop_window(
    char_presses: list[CharPress], loop_before: float, loop_after: float
) -> list[CharPress]:
    if not char_presses:
        return []

    start = max(0.0, loop_before)
    end = max(c.time for c in char_presses) - max(0.0, loop_after)
    prefix = max(0.0, -loop_before)
    suffix = max(0.0, -loop_after)

    result = [
        CharPress(c.char, c.is_press, time=c.time - start + prefix)
        for c in char_presses
        if start <= c.time <= end
    ]
    if result and suffix:
        result.append(CharPress(time=result[-1].time + suffix))
    return result


def _exit_with_missing_text() -> NoReturn:
    sys.stderr.write(
        'Required options were not provided: TEXT\n'
        'For full helptext, run tuney --help\n'
    )
    sys.exit(2)
