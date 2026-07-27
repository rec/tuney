from __future__ import annotations

import json
import random
import string
import sys
import tomllib
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import tomlkit

from ..audio.mixer import NotePress
from ..audio.player import Player
from ..config.serialize import serialize
from ..config.text_file import read_text_file
from ..midi.file import MIDI_FILE_TICKS_PER_BEAT, is_midi_file, write_midi_file
from ..presets import is_str_dict, merged_data, read_preset
from ..scale.accidentals import Accidentals
from ..scale.tuning import Computed, Type
from ..time import to_ms
from ..time.char_press import CharPress
from ..time.sequencer import Sequencer
from .app_members import AppMembers
from .platform_info import (
    acquire_single_instance,
    exit_with_message,
    instrument,
    mark_session_clean_exit,
    mark_session_started,
    release_single_instance,
    report_error,
    show_already_running,
    start_crash_logging,
    trace,
)

if TYPE_CHECKING:
    from ..ui.main_window import MainWindow


class _WindowRect(Protocol):
    def x(self) -> int: ...

    def y(self) -> int: ...

    def width(self) -> int: ...

    def height(self) -> int: ...


class App(AppMembers):
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    def run(self) -> None:
        instrument('run', gui=self.gui, frozen=getattr(sys, 'frozen', False))
        if self.gui:
            start_crash_logging()
            if not acquire_single_instance():
                show_already_running()
                return
            try:
                crashed = mark_session_started()
                restore_error = None
                try:
                    instrument('autosave restore start')
                    restore_error = self._autosave.restore(self)
                    instrument('autosave restore end', error=restore_error is not None)
                except Exception as error:
                    instrument('autosave restore exception', error=repr(error))
                    restore_error = error
                instrument('main window construct start')
                main_window = self.main_window
                instrument('main window construct end')
                if crashed:
                    main_window.show_crash_report()
                if restore_error is not None:
                    main_window.show_restore_error(restore_error)
                self.start()
                instrument('mainloop start')
                main_window.mainloop()
                mark_session_clean_exit()
                instrument('mainloop end')
            finally:
                release_single_instance()
        else:
            self.run_cli()

    def start(self) -> None:
        instrument('app start', run_in_background=self.run_in_background)
        self.main_window.start()
        self.midi_listener.start()
        self.midi.output.start()
        self.midi.output.send_tuning_dump(self.scale, self.tuning)
        if self.run_in_background:
            self.keyboard_listener.start()

    def on_char(self, c: CharPress) -> None:
        if not c.is_press and c.pressed_char and c.pressed_char == c.char.swapcase():
            c = CharPress(c.pressed_char, False, c.time)
        trace('char event', char=c.char, is_press=c.is_press)
        if c.char == '\b' and not c.is_press:
            self.stop_backspace_repeat()
        if self._is_listening:
            if c.char != '\b' or (c.is_press and self.char_presses):
                self.main_window.history.checkpoint_undo()
            recorded = self.key_recorder.recorded_char_press(
                c, self.char_presses, self.max_gap
            )
            if c.is_press:
                if c.char != '\b':
                    self.append_char_press(recorded)
                elif self.char_presses:
                    self.key_recorder.delete_last_char(self.char_presses)
                    self.start_backspace_repeat()
                self.main_window.update_text_display()
            else:
                if c.char != '\b':
                    self.append_char_press(recorded)
            self.play_char(c)

    def append_char_press(self, c: CharPress) -> None:
        self.char_presses.append(c)
        if len(self.char_presses) > 1 and c < (d := self.char_presses[-2]):
            report_error(f'Out-of-order char_press: {c} follows {d}')
            self.char_presses.sort()

    def start_backspace_repeat(self) -> None:
        self.stop_backspace_repeat()
        if self.backspace_repeat_delay >= 0 and self.backspace_repeat_rate > 0:
            self.key_recorder.backspace_repeat_after_id = self.main_window.after(
                round(to_ms(self.backspace_repeat_delay)),
                lambda: self.repeat_backspace(),
            )

    def repeat_backspace(self) -> None:
        self.key_recorder.backspace_repeat_after_id = None
        if not self._is_listening or not self.char_presses:
            return
        self.main_window.history.checkpoint_undo()
        self.key_recorder.delete_last_char(self.char_presses)
        self.main_window.update_text_display()
        self.play_char(CharPress('\b', time=0))
        if self.char_presses:
            self.key_recorder.backspace_repeat_after_id = self.main_window.after(
                round(1000 / self.backspace_repeat_rate),
                lambda: self.repeat_backspace(),
            )

    def stop_backspace_repeat(self) -> None:
        if self.key_recorder.backspace_repeat_after_id is not None:
            self.main_window.after_cancel(self.key_recorder.backspace_repeat_after_id)
            self.key_recorder.backspace_repeat_after_id = None

    def clear(self) -> None:
        instrument('clear')
        main_window = self.__dict__.get('main_window')
        if main_window is None and self.gui:
            main_window = self.main_window
        data = type(self)(gui=self.gui).dump_data()
        if main_window is not None and self.dump_data() != data:
            main_window.history.checkpoint_undo()
        self.restore_data(data)
        self.key_recorder.clear()
        if main_window is not None:
            main_window.ui.rebuild_control_panel()
            main_window.ui.rebuild_note_grid()
            main_window.sync_config_actions()
            main_window.update_text_display()

    def randomize_timing(self) -> None:
        instrument('randomize timing')
        if not (text := self.display_text):
            return
        if self.gui:
            self.main_window.history.checkpoint_undo()
        self.__dict__['char_presses'] = list(self.text_timings.char_presses(text))
        self.key_recorder.clear()
        if self.gui:
            self.main_window.update_text_display()

    def randomize_settings(self, rng: random.Random | None = None) -> None:
        instrument('randomize settings')
        rng = rng or random.Random()
        if self.gui:
            self.main_window.history.checkpoint_undo()
        intervals, notes = rng.choice(SCALE_CHOICES)
        self.scale = type(self.scale).model_validate(
            self.scale.model_dump()
            | {
                'note_names': string.ascii_uppercase,
                'root': rng.choice('ABCDEFG'),
                'begin': 'A',
                'end': 'G',
                'notes': notes,
                'intervals': intervals,
                'accidentals': rng.choice(list(Accidentals)),
                'offset': rng.randint(-12, 12),
            }
        )
        self.tuning = type(self.tuning).model_validate(
            self.tuning.model_dump()
            | {
                'type': Type.computed,
                'computed': Computed(
                    limit=rng.choice([0, 0, 0, 3, 5, 7, 11]),
                    notes_per_octave=sum(intervals),
                    octave_ratio=rng.choice([1.5, 2.0, 2.0, 2.0, 3.0]),
                ),
                'detune': rng.uniform(-50, 50),
                'root_frequency': rng.uniform(220, 660),
                'root_note': rng.randint(48, 72),
            }
        )
        if isinstance(player := self.__dict__.get('player'), Player):
            player.close()
        self.clear_cached_values()
        if self.gui:
            self.main_window.ui.rebuild_control_panel()
            self.main_window.ui.rebuild_note_grid()
            self.send_midi_tuning_dump()

    def load_text_file(self, path: Path) -> None:
        instrument('load text file', path=path)
        text = read_text_file(path)
        if self.gui:
            self.main_window.history.checkpoint_undo()
        self.__dict__['char_presses'] = list(self.text_timings.char_presses(text))
        self.key_recorder.clear()
        if self.gui:
            self.main_window.update_text_display()

    def save(self, path: Path) -> None:
        match path.suffix:
            case '.toml':
                text = self.dump_toml()
            case '.json':
                text = json.dumps(serialize(self.dump_data()), indent=2) + '\n'
            case _:
                raise ValueError(f'Do not understand file {path}')
        path.write_text(text)

    def save_autosave(self, path: Path) -> None:
        data = serialize(self.dump_data())
        if main_window := self.__dict__.get('main_window'):
            from ..ui.history import WindowState

            geometry = main_window.geometry()
            instrument(
                'autosave window geometry', **window_geometry_log_data(main_window)
            )
            data['loop'] = main_window.history.loop_state.model_dump()
            data['window'] = WindowState(
                x=geometry.x(),
                y=geometry.y(),
                width=geometry.width(),
                height=geometry.height(),
            ).model_dump()
        path.write_text(tomlkit.dumps(data))

    def dump_toml(self) -> str:
        return tomlkit.dumps(serialize(self.dump_data()))

    def restore_text(self, text: str) -> None:
        self.restore_data(_read_state_text(text))

    def apply_preset(self, name: str) -> None:
        instrument('apply preset', name=name)
        char_presses = self.__dict__.get('char_presses')
        data = merged_data(self.model_dump(), read_preset(name), {'preset': name})
        validated = type(self).model_validate(data)
        if isinstance(player := self.__dict__.get('player'), Player):
            player.close()
        for field in type(self).model_fields:
            setattr(self, field, getattr(validated, field))
        self.clear_cached_values()
        if char_presses is not None:
            self.__dict__['char_presses'] = char_presses
        self.send_midi_tuning_dump()

    def restore_data(self, data: dict[str, object]) -> None:
        instrument('restore data start', keys=sorted(data))
        validated = type(self).model_validate(data)
        if isinstance(player := self.__dict__.get('player'), Player):
            player.close()
        for field in type(self).model_fields:
            setattr(self, field, getattr(validated, field))
        self.clear_cached_values()
        self.send_midi_tuning_dump()
        instrument('restore data end')

    def dump_data(self) -> dict[str, object]:
        data = self.model_dump()
        mapper = data.pop('mapper')
        data = {'mapper': mapper, **data}
        if self.char_presses:
            data['text'] = [c.model_dump() for c in self.char_presses]
        return data

    def play_char(self, c: CharPress) -> None:
        if (note := self.mapper(c.char)) is not None:
            trace('play char', char=c.char, is_press=c.is_press, note=note)
            if not (
                self.midi.output.enable
                and self.midi.output.mute_audio_when_midi_enabled
            ):
                self.play_note(note, c.is_press)
            self.midi.output.send_note(note, c.is_press)
        if self.gui:
            self.main_window.on_char(c)

    def send_midi_tuning_dump(self) -> None:
        if self.gui and 'main_window' in self.__dict__:
            self.midi.output.send_tuning_dump(self.scale, self.tuning)

    def play_note(self, note: int, is_press: bool) -> None:
        trace('play note', is_press=is_press, note=note)
        if not self.silent:
            self.player.on_note(note, is_press)

    def clear_cached_values(self) -> None:
        keep = {
            'main_window',
            'keyboard_listener',
            'key_recorder',
            'audio_recorder',
        }
        for key in tuple(self.__dict__):
            if key not in keep and key not in type(self).model_fields:
                self.__dict__.pop(key, None)

    def on_replay(self) -> None:
        self.key_recorder.on_replay(self)

    def replay_char_presses(self) -> list[CharPress]:
        char_presses = self._loop_window(
            self.replay_source_char_presses(),
            self.main_window.history.loop_before * 1000,
            self.main_window.history.loop_after * 1000,
        )
        if self.main_window.history.loop_tempo == 1:
            return char_presses
        return [
            CharPress(
                c.char,
                c.is_press,
                time=c.time / self.main_window.history.loop_tempo,
            )
            for c in char_presses
        ]

    def replay_source_char_presses(self) -> list[CharPress]:
        if (
            self.main_window.history.loop_replay
            and self.main_window.history.randomize_on_each_loop
        ):
            return list(self.text_timings.char_presses(self.display_text))
        return self.char_presses

    def stop_replaying(self) -> None:
        self.main_window.is_replaying = False

    def run_cli(self) -> None:
        if not self.char_presses:
            exit_with_message(
                'Required options were not provided: TEXT\n'
                'For full helptext, run tuney --help',
                2,
            )

        if self.silent and not self.output:
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

        midi_file_output = self.output is not None and is_midi_file(self.output)
        try:
            if self.output and midi_file_output:
                write_midi_file(
                    self.output,
                    self.note_events(MIDI_FILE_TICKS_PER_BEAT),
                    self.midi.output,
                )
            elif self.output and self.silent:
                self.player.render_file(
                    self.output, self.note_events(self.player.sample_rate), comment
                )
            else:
                if self.output:
                    self.player.start_recording(self.output, comment)
                self.play_cli()
            completed = True
        finally:
            if not (self.silent or midi_file_output):
                self.player.stop_all()
                self.player.wait()
                if self.output:
                    self.player.stop_recording()
                self.player.close()
            if self.output and not completed:
                self.output.unlink(missing_ok=True)

    def note_events(self, sample_rate: int) -> list[tuple[int, NotePress]]:
        events: list[tuple[int, NotePress]] = []
        for press in self.char_presses:
            if (note := self.mapper(press.char)) is not None:
                frame = round(press.time * sample_rate / 1000)
                events.append((frame, NotePress(note, press.is_press)))
        return events

    def output_comment(self) -> Callable[[], str]:
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

    def play_cli(self) -> None:
        def callback(c: CharPress | None) -> None:
            if c:
                if c.is_press:
                    print(c.char, end='', flush=True)
                self.play_char(c)

        try:
            Sequencer(char_presses=self.char_presses, callback=callback).run()
        except KeyboardInterrupt:
            print()
            raise
        print()

    def _loop_window(
        self, char_presses: list[CharPress], loop_before: float, loop_after: float
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


def window_geometry_log_data(window: MainWindow) -> dict[str, object]:
    return {
        'direct': {
            'x': window.x(),
            'y': window.y(),
            'width': window.width(),
            'height': window.height(),
        },
        'geometry': _window_rect_value(window.geometry()),
        'frame_geometry': _window_rect_value(window.frameGeometry()),
        'normal_geometry': _window_rect_value(window.normalGeometry()),
        'window_state': window.windowState(),
        'is_maximized': window.isMaximized(),
        'is_minimized': window.isMinimized(),
        'is_full_screen': window.isFullScreen(),
    }


def _window_rect_value(rect: _WindowRect) -> dict[str, int]:
    return {
        'x': rect.x(),
        'y': rect.y(),
        'width': rect.width(),
        'height': rect.height(),
    }


def _read_state_text(text: str) -> dict[str, object]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as toml_error:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as json_error:
            raise ValueError(
                f'Clipboard does not contain TOML or JSON: {json_error}'
            ) from toml_error
    if not is_str_dict(data):
        raise ValueError('Clipboard does not contain a string dictionary')
    return data


SCALE_CHOICES = [
    ([1] * 12, None),
    ([2, 2, 1, 2, 2, 2, 1], None),
    ([2, 2, 1, 2, 2, 2, 1], 'CDEFGAB'),
    ([2, 2, 3, 2, 3], None),
    ([2, 2, 3, 2, 3], 'CDFGA'),
    ([2, 2, 2, 2, 2, 2], None),
    ([3, 2, 2, 3, 2], None),
]
