from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import tomlkit
import tyro
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .audio.midi import MIDI
from .audio.mixer import NotePress
from .audio.multi_player import MultiPlayer
from .char_press import CharPress
from .keyboard.listener import KeyboardListener
from .mapper.mapper import Mapper
from .presets import merged_data, read_file, read_preset
from .serialize import serialize
from .time import Milliseconds, Seconds, to_ms
from .time.sequencer import Sequencer
from .time.text_timings import TextTimings
from .ui.transport import Action, State

if TYPE_CHECKING:
    from .ui.app import App

XDG_STATE_HOME = 'XDG_STATE_HOME'
AUTOSAVE_FILE = Path('tuney') / 'state.toml'


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
    preset: Annotated[str | None, tyro.conf.arg(aliases=['-p'])] = None

    # Load configs from a JSON or toml file
    config_file: Annotated[Path | None, tyro.conf.arg(aliases=['-c'])] = None

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
    ] = None

    # Positional text to start the program with
    text_args: Annotated[
        list[str],
        tyro.conf.Positional,
        tyro.conf.arg(name='text', metavar='TEXT'),
    ] = Field(default_factory=list, exclude=True)

    # Maximum silent gap to keep in recordings, in seconds
    max_gap: Annotated[float, tyro.conf.arg(aliases=['-m'])] = 4.0

    # Time to hover over a widget before showing help, in seconds
    hover_time: float = 1.0

    # Time to hold backspace before it starts repeating, in seconds
    backspace_repeat_delay: float = 2.0

    # Backspace repeats per second after backspace_repeat_delay
    backspace_repeat_rate: float = 4.0

    # Open the graphical interface
    gui: Annotated[bool, tyro.conf.arg(aliases=['-g'])] = False

    # Disable synthesized audio output
    silent: Annotated[bool, tyro.conf.arg(aliases=['-s'])] = False

    # Audio file to write while playing text
    output: Annotated[Path | None, tyro.conf.arg(aliases=['-o'])] = None

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: Annotated[bool, tyro.conf.arg(aliases=['-b'])] = False

    # Path to the automatically saved GUI state
    autosave_file: tyro.conf.Suppress[Path | None] = Field(default=None, exclude=True)

    model_config = ConfigDict(exclude=['_sequencer'])  # ty:ignore[invalid-key]

    _sequencer: Sequencer | None = None
    _recording_start_time: Seconds | None = None
    _recording_time_offset: Milliseconds = 0.0
    _recording_insert_time: Milliseconds | None = None
    _replay_text: str = ''
    _audio_recording_path: Path | None = None
    _audio_recording_started: bool = False
    _audio_recording_comment: Callable[[], str] | None = None
    _backspace_repeat_after_id: str | None = None

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
            recorded = self.recorded_char_press(c)
            if c.is_press:
                if c.char != '\b':
                    self.append_char_press(recorded)
                elif self.char_presses:
                    self._delete_last_char()
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

    def _delete_last_char(self) -> None:
        deleted_time = None
        while self.char_presses:
            deleted = self.char_presses.pop()
            if deleted.is_press:
                deleted_time = deleted.time
                break
        if deleted_time is not None:
            self._recording_insert_time = deleted_time

    def _start_backspace_repeat(self) -> None:
        self._stop_backspace_repeat()
        if self.backspace_repeat_delay >= 0 and self.backspace_repeat_rate > 0:
            self._backspace_repeat_after_id = self.app.after(
                round(to_ms(self.backspace_repeat_delay)),
                self._repeat_backspace,
            )

    def _repeat_backspace(self) -> None:
        self._backspace_repeat_after_id = None
        if not self._is_listening or not self.char_presses:
            return
        self.app.record_undo()
        self._delete_last_char()
        self.app.ui.set_text(self.display_text)
        self._on_char(CharPress('\b', time=0))
        if self.char_presses:
            self._backspace_repeat_after_id = self.app.after(
                round(1000 / self.backspace_repeat_rate),
                self._repeat_backspace,
            )

    def _stop_backspace_repeat(self) -> None:
        if self._backspace_repeat_after_id is not None:
            self.app.after_cancel(self._backspace_repeat_after_id)
            self._backspace_repeat_after_id = None

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
        if self.gui and self.char_presses:
            self.app.record_undo()
        self.char_presses.clear()
        self._recording_start_time = None
        self._recording_time_offset = 0.0
        self._recording_insert_time = None
        self._replay_text = ''
        if self.gui:
            self.app.ui.set_text('')

    def randomize_timing(self) -> None:
        text = self.display_text
        if not text:
            return
        if self.gui:
            self.app.record_undo()
        self.__dict__['char_presses'] = list(self.text_timings.char_presses(text))
        self._recording_start_time = None
        self._recording_time_offset = 0.0
        self._recording_insert_time = None
        self._replay_text = ''
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

    def autosave(self) -> None:
        path = self.autosave_path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.save(path)

    def restore_autosave(self) -> None:
        if self._should_restore_autosave and self.autosave_path.exists():
            try:
                data = read_file(self.autosave_path)
            except (OSError, ValueError) as error:
                print(
                    f'Could not restore {self.autosave_path}: {error}',
                    file=sys.stderr,
                )
                return
            self.restore_autosave_data(data)

    def restore_autosave_data(self, data: dict[str, object]) -> None:
        while True:
            try:
                self.restore_data(data)
                return
            except ValidationError as error:
                print(
                    f'Could not restore fields from {self.autosave_path}: {error}',
                    file=sys.stderr,
                )
                if not any(_delete_data_path(data, e['loc']) for e in error.errors()):
                    return

    @cached_property
    def autosave_path(self) -> Path:
        if self.autosave_file is not None:
            return self.autosave_file
        state_home = os.environ.get(XDG_STATE_HOME)
        if state_home and Path(state_home).is_absolute():
            return Path(state_home) / AUTOSAVE_FILE
        return Path.home() / '.local' / 'state' / AUTOSAVE_FILE

    @property
    def _should_restore_autosave(self) -> bool:
        return (
            self.gui
            and self.config_file is None
            and self.preset is None
            and self.text is None
            and not self.text_args
        )

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
        fields = type(self).model_fields
        keep = {'app', 'listener'}
        for key in tuple(self.__dict__):
            if key not in fields and key not in keep:
                self.__dict__.pop(key, None)

    def on_transport_state(
        self,
        old_state: State,
        state: State,
        action: Action,
        path: Path | None = None,
    ) -> bool:
        if action == Action.save:
            if path is None:
                return False
            if old_state == State.recording:
                self._stop_audio_recording()
            self._save_audio_recording(path)
        elif action == Action.clear:
            if old_state == State.recording:
                self._stop_audio_recording()
            self._clear_audio_recording()
        elif state == State.paused:
            self._stop_audio_recording()
        else:
            self._start_audio_recording()
        return True

    def _start_audio_recording(self) -> None:
        if self._audio_recording_path is None:
            self._audio_recording_path = (
                Path(tempfile.gettempdir()) / f'tuney-{uuid.uuid4()}.wav'
            )
            self._audio_recording_path.touch()
            self._audio_recording_comment = self._output_comment()
        assert self._audio_recording_path is not None
        self.player.start_recording(
            self._audio_recording_path,
            self._audio_recording_comment,
            append=self._audio_recording_started,
        )
        self._audio_recording_started = True

    def _stop_audio_recording(self) -> None:
        self.player.stop_recording()

    def _save_audio_recording(self, path: Path) -> None:
        if self._audio_recording_path is None:
            return
        self._audio_recording_path.replace(path)
        self._audio_recording_path = None
        self._audio_recording_started = False
        self._audio_recording_comment = None

    def _clear_audio_recording(self) -> None:
        if self._audio_recording_path is not None:
            self._audio_recording_path.unlink(missing_ok=True)
        self._audio_recording_path = None
        self._audio_recording_started = False
        self._audio_recording_comment = None

    @property
    def _is_listening(self) -> bool:
        return (
            not self.app.is_replaying
            and not self.app.is_saving
            and not self.app.focus_in_control_panel
            and (self.run_in_background or self.app.has_focus)
        )

    def on_replay(self) -> None:
        self.player.stop_all()

        sequencer, self._sequencer = self._sequencer, None
        if sequencer:
            sequencer.stop()

        if self.app.is_replaying:
            self._replay_text = ''
            self.app.ui.set_text(self._replay_text)
            self._sequencer = Sequencer(
                char_presses=self._replay_char_presses(), callback=self._on_replay
            )
            self._sequencer.start()
        else:
            self._replay_text = ''
            self.app.ui.set_text(self.display_text)

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

    def _on_replay(self, c: CharPress | None) -> None:
        if c:
            if c.is_press:
                self._replay_text += c.char
                self.app.after(0, self.app.ui.set_text, self._replay_text)
            self._on_char(c)
        elif self.app.is_replaying and self._sequencer is not None:
            self.app.after(0, self._finish_replay)

    def _finish_replay(self) -> None:
        if self.app.loop_replay and self._replay_char_presses():
            self.on_replay()
            return
        self.player.stop_all()
        self.app.is_replaying = False

    def __call__(self) -> None:
        if self.gui:
            self.restore_autosave()
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
        try:
            if self.output and self.silent:
                self.player.render_file(
                    self.output, self._note_events(), self._output_comment()
                )
            else:
                if self.output:
                    self.player.start_recording(self.output, self._output_comment())
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


def _delete_data_path(data: dict[str, object], loc: tuple[object, ...]) -> bool:
    current: object = data
    for part in loc[:-1]:
        if isinstance(part, str) and isinstance(current, dict):
            current = current.get(part)
        elif isinstance(part, int) and isinstance(current, list):
            if part < 0 or part >= len(current):
                return False
            current = current[part]
        else:
            return False
    if not loc:
        return False
    last = loc[-1]
    if isinstance(last, str) and isinstance(current, dict) and last in current:
        del current[last]
        return True
    if isinstance(last, int) and isinstance(current, list):
        if last < 0 or last >= len(current):
            return False
        del current[last]
        return True
    return False


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
