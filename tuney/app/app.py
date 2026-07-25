from __future__ import annotations

import json
import random
import string
import sys
import tomllib
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit

from ..audio.mixer import NotePress
from ..audio.player import Player
from ..config.serialize import serialize
from ..config.text_file import read_text_file
from ..config.tuney import Tuney
from ..keyboard.listener import KeyboardListener
from ..midi.file import MIDI_FILE_TICKS_PER_BEAT, is_midi_file, write_midi_file
from ..midi.midi import MidiListener
from ..presets import is_str_dict, merged_data, read_preset
from ..presets.autosave import Autosave
from ..scale.accidentals import Accidentals
from ..scale.tuning import Computed, Type
from ..time import to_ms
from ..time.char_press import CharPress
from ..time.sequencer import Sequencer
from ..ui import startup
from .audio_recorder import AudioRecorder
from .global_config import GlobalConfig
from .key_recorder import KeyRecorder
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
from .text_timing import text_timing_rows

if TYPE_CHECKING:
    from ..ui.main_window import MainWindow


class App(Tuney):
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    @cached_property
    def main_window(self) -> MainWindow:
        assert self.gui
        from ..ui.main_window import MainWindow

        return MainWindow(self)

    @cached_property
    def keyboard_listener(self) -> KeyboardListener:
        return KeyboardListener(
            self.main_window.on_key if self.gui else lambda c: on_char(self, c)
        )

    @cached_property
    def midi_listener(self) -> MidiListener:
        return self.midi.listener(
            lambda note, is_press: play_note(self, note, is_press)
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


def run(app: App) -> None:
    instrument('run', gui=app.gui, frozen=getattr(sys, 'frozen', False))
    if app.gui:
        start_crash_logging()
        if not acquire_single_instance():
            show_already_running()
            return
        try:
            crashed = mark_session_started()
            restore_error = None
            try:
                instrument('autosave restore start')
                restore_error = app._autosave.restore(app)
                instrument('autosave restore end', error=restore_error is not None)
            except Exception as error:
                instrument('autosave restore exception', error=repr(error))
                restore_error = error
            instrument('main window construct start')
            main_window = app.main_window
            instrument('main window construct end')
            if crashed:
                main_window.show_crash_report()
            if restore_error is not None:
                main_window.show_restore_error(restore_error)
            start(app)
            instrument('mainloop start')
            main_window.mainloop()
            mark_session_clean_exit()
            instrument('mainloop end')
        finally:
            release_single_instance()
    else:
        run_cli(app)


def start(app: App) -> None:
    instrument('app start', run_in_background=app.run_in_background)
    app.main_window.start()
    app.midi_listener.start()
    app.midi.output.start()
    app.midi.output.send_tuning_dump(app.scale, app.tuning)
    if app.run_in_background:
        app.keyboard_listener.start()


def on_char(app: App, c: CharPress) -> None:
    trace('char event', char=c.char, is_press=c.is_press)
    if c.char == '\b' and not c.is_press:
        stop_backspace_repeat(app)
    if app._is_listening:
        if c.char != '\b' or (c.is_press and app.char_presses):
            app.main_window.history.checkpoint_undo()
        recorded = app.key_recorder.recorded_char_press(
            c, app.char_presses, app.max_gap
        )
        if c.is_press:
            if c.char != '\b':
                append_char_press(app, recorded)
            elif app.char_presses:
                app.key_recorder.delete_last_char(app.char_presses)
                start_backspace_repeat(app)
            app.main_window.update_text_display()
        else:
            if c.char != '\b':
                append_char_press(app, recorded)
            play_char(app, CharPress(c.char.swapcase(), False))
        play_char(app, c)


def append_char_press(app: App, c: CharPress) -> None:
    app.char_presses.append(c)
    if len(app.char_presses) > 1 and c < (d := app.char_presses[-2]):
        report_error(f'Out-of-order char_press: {c} follows {d}')
        app.char_presses.sort()


def start_backspace_repeat(app: App) -> None:
    stop_backspace_repeat(app)
    if app.backspace_repeat_delay >= 0 and app.backspace_repeat_rate > 0:
        app.key_recorder.backspace_repeat_after_id = app.main_window.after(
            round(to_ms(app.backspace_repeat_delay)),
            lambda: repeat_backspace(app),
        )


def repeat_backspace(app: App) -> None:
    app.key_recorder.backspace_repeat_after_id = None
    if not app._is_listening or not app.char_presses:
        return
    app.main_window.history.checkpoint_undo()
    app.key_recorder.delete_last_char(app.char_presses)
    app.main_window.update_text_display()
    play_char(app, CharPress('\b', time=0))
    if app.char_presses:
        app.key_recorder.backspace_repeat_after_id = app.main_window.after(
            round(1000 / app.backspace_repeat_rate),
            lambda: repeat_backspace(app),
        )


def stop_backspace_repeat(app: App) -> None:
    if app.key_recorder.backspace_repeat_after_id is not None:
        app.main_window.after_cancel(app.key_recorder.backspace_repeat_after_id)
        app.key_recorder.backspace_repeat_after_id = None


def clear(app: App) -> None:
    instrument('clear')
    main_window = app.__dict__.get('main_window')
    if main_window is None and app.gui:
        main_window = app.main_window
    data = dump_data(App(gui=app.gui))
    if main_window is not None and dump_data(app) != data:
        main_window.history.checkpoint_undo()
    restore_data(app, data)
    app.key_recorder.clear()
    if main_window is not None:
        main_window.ui.rebuild_control_panel()
        main_window.ui.rebuild_note_grid()
        main_window.sync_config_actions()
        main_window.update_text_display()


def randomize_timing(app: App) -> None:
    instrument('randomize timing')
    if not (text := app.display_text):
        return
    if app.gui:
        app.main_window.history.checkpoint_undo()
    app.__dict__['char_presses'] = list(app.text_timings.char_presses(text))
    app.key_recorder.clear()
    if app.gui:
        app.main_window.update_text_display()


def randomize_settings(app: App, rng: random.Random | None = None) -> None:
    instrument('randomize settings')
    rng = rng or random.Random()
    if app.gui:
        app.main_window.history.checkpoint_undo()
    intervals, notes = rng.choice(SCALE_CHOICES)
    app.scale = type(app.scale).model_validate(
        app.scale.model_dump()
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
    app.tuning = type(app.tuning).model_validate(
        app.tuning.model_dump()
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
    if isinstance(player := app.__dict__.get('player'), Player):
        player.close()
    clear_cached_values(app)
    if app.gui:
        app.main_window.ui.rebuild_control_panel()
        app.main_window.ui.rebuild_note_grid()
        send_midi_tuning_dump(app)


def load_text_file(app: App, path: Path) -> None:
    instrument('load text file', path=path)
    text = read_text_file(path)
    if app.gui:
        app.main_window.history.checkpoint_undo()
    app.__dict__['char_presses'] = list(app.text_timings.char_presses(text))
    app.key_recorder.clear()
    if app.gui:
        app.main_window.update_text_display()


def save(app: App, path: Path) -> None:
    match path.suffix:
        case '.toml':
            text = dump_toml(app)
        case '.json':
            text = json.dumps(serialize(dump_data(app)), indent=2) + '\n'
        case _:
            raise ValueError(f'Do not understand file {path}')
    path.write_text(text)


def save_autosave(app: App, path: Path) -> None:
    data = serialize(dump_data(app))
    if main_window := app.__dict__.get('main_window'):
        from ..ui.history import WindowState

        geometry = main_window.geometry()
        data['loop'] = main_window.history.loop_state.model_dump()
        data['window'] = WindowState(
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height(),
        ).model_dump()
    path.write_text(tomlkit.dumps(data))


def dump_toml(app: App) -> str:
    return tomlkit.dumps(serialize(dump_data(app)))


def restore_text(app: App, text: str) -> None:
    restore_data(app, _read_state_text(text))


def apply_preset(app: App, name: str) -> None:
    instrument('apply preset', name=name)
    char_presses = app.__dict__.get('char_presses')
    data = merged_data(app.model_dump(), read_preset(name), {'preset': name})
    validated = type(app).model_validate(data)
    if isinstance(player := app.__dict__.get('player'), Player):
        player.close()
    for field in type(app).model_fields:
        setattr(app, field, getattr(validated, field))
    clear_cached_values(app)
    if char_presses is not None:
        app.__dict__['char_presses'] = char_presses
    send_midi_tuning_dump(app)


def restore_data(app: App, data: dict[str, object]) -> None:
    instrument('restore data start', keys=sorted(data))
    validated = type(app).model_validate(data)
    if isinstance(player := app.__dict__.get('player'), Player):
        player.close()
    for field in type(app).model_fields:
        setattr(app, field, getattr(validated, field))
    clear_cached_values(app)
    send_midi_tuning_dump(app)
    instrument('restore data end')


def dump_data(app: App) -> dict[str, object]:
    data = app.model_dump()
    mapper = data.pop('mapper')
    data = {'mapper': mapper, **data}
    if app.char_presses:
        data['text'] = [c.model_dump() for c in app.char_presses]
    return data


def play_char(app: App, c: CharPress) -> None:
    if (note := app.mapper(c.char)) is not None:
        trace('play char', char=c.char, is_press=c.is_press, note=note)
        if not (
            app.midi.output.enable and app.midi.output.mute_audio_when_midi_enabled
        ):
            play_note(app, note, c.is_press)
        app.midi.output(note, c.is_press)
    if app.gui:
        app.main_window.on_char(c)


def send_midi_tuning_dump(app: App) -> None:
    if app.gui and 'main_window' in app.__dict__:
        app.midi.output.send_tuning_dump(app.scale, app.tuning)


def play_note(app: App, note: int, is_press: bool) -> None:
    trace('play note', is_press=is_press, note=note)
    if not app.silent:
        app.player.on_note(note, is_press)


def clear_cached_values(app: App) -> None:
    keep = {
        'main_window',
        'keyboard_listener',
        'key_recorder',
        'audio_recorder',
    }
    for key in tuple(app.__dict__):
        if key not in keep and key not in type(app).model_fields:
            app.__dict__.pop(key, None)


def on_replay(app: App) -> None:
    app.key_recorder.on_replay(app)


def replay_char_presses(app: App) -> list[CharPress]:
    char_presses = _loop_window(
        replay_source_char_presses(app),
        app.main_window.history.loop_before * 1000,
        app.main_window.history.loop_after * 1000,
    )
    if app.main_window.history.loop_tempo == 1:
        return char_presses
    return [
        CharPress(
            c.char,
            c.is_press,
            time=c.time / app.main_window.history.loop_tempo,
        )
        for c in char_presses
    ]


def replay_source_char_presses(app: App) -> list[CharPress]:
    if (
        app.main_window.history.loop_replay
        and app.main_window.history.randomize_on_each_loop
    ):
        return list(app.text_timings.char_presses(app.display_text))
    return app.char_presses


def stop_replaying(app: App) -> None:
    app.main_window.is_replaying = False


def run_cli(app: App) -> None:
    if not app.char_presses:
        exit_with_message(
            'Required options were not provided: TEXT\n'
            'For full helptext, run tuney --help',
            2,
        )

    if app.silent and not app.output:
        exit_with_message('CLI mode requires sound')

    completed = False
    start_time = datetime.now(timezone.utc)

    def comment() -> str:
        return tomlkit.dumps(
            {
                'original_text': app.display_text,
                'recording_start_time': start_time.isoformat(),
                'recording_finish_time': datetime.now(timezone.utc).isoformat(),
                'settings': tomlkit.dumps(serialize(dump_data(app))),
            }
        )

    midi_file_output = app.output is not None and is_midi_file(app.output)
    try:
        if app.output and midi_file_output:
            write_midi_file(
                app.output,
                note_events(app, MIDI_FILE_TICKS_PER_BEAT),
                app.midi.output,
            )
        elif app.output and app.silent:
            app.player.render_file(
                app.output, note_events(app, app.player.sample_rate), comment
            )
        else:
            if app.output:
                app.player.start_recording(app.output, comment)
            play_cli(app)
        completed = True
    finally:
        if not (app.silent or midi_file_output):
            app.player.stop_all()
            app.player.wait()
            if app.output:
                app.player.stop_recording()
            app.player.close()
        if app.output and not completed:
            app.output.unlink(missing_ok=True)


def note_events(app: App, sample_rate: int) -> list[tuple[int, NotePress]]:
    events: list[tuple[int, NotePress]] = []
    for press in app.char_presses:
        if (note := app.mapper(press.char)) is not None:
            frame = round(press.time * sample_rate / 1000)
            events.append((frame, NotePress(note, press.is_press)))
    return events


def output_comment(app: App) -> Callable[[], str]:
    start_time = datetime.now(timezone.utc)

    def comment() -> str:
        return tomlkit.dumps(
            {
                'original_text': app.display_text,
                'recording_start_time': start_time.isoformat(),
                'recording_finish_time': datetime.now(timezone.utc).isoformat(),
                'settings': tomlkit.dumps(serialize(dump_data(app))),
            }
        )

    return comment


def play_cli(app: App) -> None:
    def callback(c: CharPress | None) -> None:
        if c:
            if c.is_press:
                print(c.char, end='', flush=True)
            play_char(app, c)

    try:
        Sequencer(char_presses=app.char_presses, callback=callback).run()
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
