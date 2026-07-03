from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit

from .audio.mixer import NotePress
from .keyboard.char_press import CharPress
from .keyboard.listener import KeyboardListener
from .platform_info import exit_with_message, report_error
from .presets import merged_data, read_preset
from .presets.autosave import Autosave
from .recorders.audio_recorder import AudioRecorder
from .recorders.key_recorder import KeyRecorder
from .serialize import serialize
from .time import to_ms
from .time.sequencer import Sequencer

if TYPE_CHECKING:
    from .tuney import Tuney
    from .ui.main_window import MainWindow


class TuneyState:
    def __init__(self, tuney: Tuney) -> None:
        self.tuney = tuney

    @cached_property
    def app(self) -> MainWindow:
        assert self.tuney.gui
        from .ui.main_window import MainWindow

        return MainWindow(self.tuney)

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self.app.on_key if self.tuney.gui else self.on_char)

    @cached_property
    def note_labels(self) -> dict[str, str]:
        return {
            c: '\n'.join([self.tuney.player.scale.to_name(n), ' ' + c])
            for c, n in self.tuney.mapper.char_to_number.items()
        }

    @cached_property
    def key_recorder(self) -> KeyRecorder:
        return KeyRecorder()

    @cached_property
    def audio_recorder(self) -> AudioRecorder:
        return AudioRecorder()

    @cached_property
    def char_presses(self) -> list[CharPress]:
        if self.tuney.text_file is not None:
            return list(
                self.tuney.text_timings.char_presses(self.tuney.text_file.read_text())
            )
        if self.tuney.text is None:
            return []
        if isinstance(self.tuney.text, list):
            return self.tuney.text
        return list(self.tuney.text_timings.char_presses(self.tuney.text))

    @property
    def display_text(self) -> str:
        return ''.join(c.char for c in self.char_presses if c.is_press)

    def on_char(self, c: CharPress) -> None:
        if c.char == '\b' and not c.is_press:
            self._stop_backspace_repeat()
        if self._is_listening:
            if c.char != '\b' or (c.is_press and self.char_presses):
                self.app.history.checkpoint_undo()
            recorded = self.key_recorder.recorded_char_press(
                c, self.char_presses, self.tuney.max_gap
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
            report_error(f'Out-of-order char_press: {c} follows {d}')
            self.char_presses.sort()

    def _start_backspace_repeat(self) -> None:
        self._stop_backspace_repeat()
        if (
            self.tuney.backspace_repeat_delay >= 0
            and self.tuney.backspace_repeat_rate > 0
        ):
            self.key_recorder.backspace_repeat_after_id = self.app.after(
                round(to_ms(self.tuney.backspace_repeat_delay)),
                self._repeat_backspace,
            )

    def _repeat_backspace(self) -> None:
        self.key_recorder.backspace_repeat_after_id = None
        if not self._is_listening or not self.char_presses:
            return
        self.app.history.checkpoint_undo()
        self.key_recorder.delete_last_char(self.char_presses)
        self.app.ui.set_text(self.display_text)
        self._on_char(CharPress('\b', time=0))
        if self.char_presses:
            self.key_recorder.backspace_repeat_after_id = self.app.after(
                round(1000 / self.tuney.backspace_repeat_rate),
                self._repeat_backspace,
            )

    def _stop_backspace_repeat(self) -> None:
        if self.key_recorder.backspace_repeat_after_id is not None:
            self.app.after_cancel(self.key_recorder.backspace_repeat_after_id)
            self.key_recorder.backspace_repeat_after_id = None

    def clear(self) -> None:
        if self.tuney.gui and self.char_presses:
            self.app.history.checkpoint_undo()
        self.char_presses.clear()
        self.key_recorder.clear()
        if self.tuney.gui:
            self.app.ui.set_text('')

    def randomize_timing(self) -> None:
        text = self.display_text
        if not text:
            return
        if self.tuney.gui:
            self.app.history.checkpoint_undo()
        self.__dict__['char_presses'] = list(self.tuney.text_timings.char_presses(text))
        self.key_recorder.clear()
        if self.tuney.gui:
            self.app.ui.set_text(text)

    def load_text_file(self, path: Path) -> None:
        text = path.read_text()
        if self.tuney.gui:
            self.app.history.checkpoint_undo()
        self.__dict__['char_presses'] = list(self.tuney.text_timings.char_presses(text))
        self.key_recorder.clear()
        if self.tuney.gui:
            self.app.ui.set_text(self.display_text)

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
        return Autosave(file=self.tuney.autosave_file)

    def apply_preset(self, name: str) -> None:
        char_presses = self.__dict__.get('char_presses')
        data = merged_data(self.tuney.model_dump(), read_preset(name), {'preset': name})
        validated = type(self.tuney).model_validate(data)
        for field in type(self.tuney).model_fields:
            object.__setattr__(self.tuney, field, getattr(validated, field))
        self._clear_cached_values()
        if char_presses is not None:
            self.__dict__['char_presses'] = char_presses

    def restore_data(self, data: dict[str, object]) -> None:
        autosave_file = self.tuney.autosave_file
        validated = type(self.tuney).model_validate(data)
        for field in type(self.tuney).model_fields:
            object.__setattr__(self.tuney, field, getattr(validated, field))
        if 'autosave_file' not in data:
            object.__setattr__(self.tuney, 'autosave_file', autosave_file)
        self._clear_cached_values()

    def dump_data(self) -> dict[str, object]:
        data = self.tuney.model_dump()
        if self.char_presses:
            data['text'] = [c.model_dump() for c in self.char_presses]
        return data

    def _on_char(self, c: CharPress) -> None:
        if (note := self.tuney.mapper(c.char)) is not None:
            if not self.tuney.silent:
                self.tuney.player.on_note(note, c.is_press)
            self.tuney.midi(note, c.is_press)
        if self.tuney.gui:
            self.app.on_char(c)

    def _clear_cached_values(self) -> None:
        keep = {'tuney', 'app', 'listener', 'key_recorder', 'audio_recorder'}
        for key in tuple(self.__dict__):
            if key not in keep:
                self.__dict__.pop(key, None)

    @property
    def _is_listening(self) -> bool:
        return (
            not self.app.is_replaying
            and not self.app.is_saving
            and not self.app.focus_in_control_panel
            and (self.tuney.run_in_background or self.app.has_focus)
        )

    def on_replay(self) -> None:
        self.key_recorder.on_replay(self)

    def _replay_char_presses(self) -> list[CharPress]:
        char_presses = _loop_window(
            self._replay_source_char_presses(),
            self.app.history.loop_before * 1000,
            self.app.history.loop_after * 1000,
        )
        if self.app.history.loop_tempo == 1:
            return char_presses
        return [
            CharPress(c.char, c.is_press, time=c.time / self.app.history.loop_tempo)
            for c in char_presses
        ]

    def _replay_source_char_presses(self) -> list[CharPress]:
        if self.app.history.loop_replay and self.app.history.randomize_on_each_loop:
            return list(self.tuney.text_timings.char_presses(self.display_text))
        return self.char_presses

    def _stop_replaying(self) -> None:
        self.app.is_replaying = False

    def __call__(self) -> None:
        if self.tuney.gui:
            self._autosave.restore(self.tuney)
            self.start()
            self.app.mainloop()
        else:
            self._run_cli()

    def start(self) -> None:
        self.app.start()
        if self.tuney.run_in_background:
            self.listener.start()

    def _run_cli(self) -> None:
        if not self.char_presses:
            exit_with_message(
                'Required options were not provided: TEXT\n'
                'For full helptext, run tuney --help',
                2,
            )

        if self.tuney.silent and not self.tuney.output:
            exit_with_message('CLI mode requires sound')

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
            if self.tuney.output and self.tuney.silent:
                self.tuney.player.render_file(
                    self.tuney.output, self._note_events(), comment
                )
            else:
                if self.tuney.output:
                    self.tuney.player.start_recording(self.tuney.output, comment)
                self._play_cli()
            completed = True
        finally:
            if not self.tuney.silent:
                self.tuney.player.stop_all()
                self.tuney.player.wait()
                if self.tuney.output:
                    self.tuney.player.stop_recording()
                self.tuney.player.close()
            if self.tuney.output and not completed:
                self.tuney.output.unlink(missing_ok=True)

    def _note_events(self) -> list[tuple[int, NotePress]]:
        events: list[tuple[int, NotePress]] = []
        for press in self.char_presses:
            if (note := self.tuney.mapper(press.char)) is not None:
                frame = round(press.time * self.tuney.player.sample_rate / 1000)
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
