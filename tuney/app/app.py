from __future__ import annotations

import json
import tomllib
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit

from ..audio.mixer import NotePress
from ..audio.player import Player
from ..cfg.serialize import serialize
from ..cfg.text_file import read_text_file
from ..cfg.tuney import Tuney
from ..keyboard.listener import KeyboardListener
from ..presets import is_str_dict, merged_data, read_preset
from ..presets.autosave import Autosave
from ..recorders.audio_recorder import AudioRecorder
from ..recorders.key_recorder import KeyRecorder
from ..time import to_ms
from ..time.char_press import CharPress
from ..time.sequencer import Sequencer
from .platform_info import exit_with_message, report_error

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
    def listener(self) -> KeyboardListener:
        return KeyboardListener(
            self.main_window.on_key if self.gui else lambda c: on_char(self, c)
        )

    @cached_property
    def player(self) -> Player:
        return Player(
            device=self.device,
            sound=self.sound,
            scale=self.scale,
            tuning=self.tuning,
        )

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

    @cached_property
    def _autosave(self) -> Autosave:
        return Autosave(file=self.autosave_file)

    @property
    def _is_listening(self) -> bool:
        return (
            not self.main_window.is_replaying
            and not self.main_window.is_saving
            and not self.main_window.focus_in_control_panel
            and (self.run_in_background or self.main_window.has_focus)
        )


def run(app: App) -> None:
    if app.gui:
        restore_error = None
        try:
            restore_error = app._autosave.restore(app)
        except Exception as error:
            restore_error = error
        main_window = app.main_window
        if restore_error is not None:
            main_window.show_restore_error(restore_error)
        start(app)
        main_window.mainloop()
    else:
        run_cli(app)


def start(app: App) -> None:
    app.main_window.start()
    if app.run_in_background:
        app.listener.start()


def on_char(app: App, c: CharPress) -> None:
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
            app.main_window.ui.set_text(app.display_text)
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
    app.main_window.ui.set_text(app.display_text)
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
    main_window = app.__dict__.get('main_window')
    if main_window is None and app.gui:
        main_window = app.main_window
    if main_window is not None and app.char_presses:
        main_window.history.checkpoint_undo()
    app.char_presses.clear()
    app.key_recorder.clear()
    if main_window is not None:
        main_window.ui.set_text('')


def randomize_timing(app: App) -> None:
    if not (text := app.display_text):
        return
    if app.gui:
        app.main_window.history.checkpoint_undo()
    app.__dict__['char_presses'] = list(app.text_timings.char_presses(text))
    app.key_recorder.clear()
    if app.gui:
        app.main_window.ui.set_text(text)


def load_text_file(app: App, path: Path) -> None:
    text = read_text_file(path)
    if app.gui:
        app.main_window.history.checkpoint_undo()
    app.__dict__['char_presses'] = list(app.text_timings.char_presses(text))
    app.key_recorder.clear()
    if app.gui:
        app.main_window.ui.set_text(app.display_text)


def save(app: App, path: Path) -> None:
    match path.suffix:
        case '.toml':
            text = dump_toml(app)
        case '.json':
            text = json.dumps(serialize(dump_data(app)), indent=2) + '\n'
        case _:
            raise ValueError(f'Do not understand file {path}')
    path.write_text(text)


def dump_toml(app: App) -> str:
    return tomlkit.dumps(serialize(dump_data(app)))


def restore_text(app: App, text: str) -> None:
    restore_data(app, _read_state_text(text))


def apply_preset(app: App, name: str) -> None:
    char_presses = app.__dict__.get('char_presses')
    data = merged_data(app.model_dump(), read_preset(name), {'preset': name})
    validated = type(app).model_validate(data)
    for field in type(app).model_fields:
        object.__setattr__(app, field, getattr(validated, field))
    clear_cached_values(app)
    if char_presses is not None:
        app.__dict__['char_presses'] = char_presses


def restore_data(app: App, data: dict[str, object]) -> None:
    autosave_file = app.autosave_file
    validated = type(app).model_validate(data)
    for field in type(app).model_fields:
        object.__setattr__(app, field, getattr(validated, field))
    if 'autosave_file' not in data:
        object.__setattr__(app, 'autosave_file', autosave_file)
    clear_cached_values(app)


def dump_data(app: App) -> dict[str, object]:
    data = app.model_dump()
    mapper = data.pop('mapper')
    data = {'mapper': mapper, **data}
    if app.char_presses:
        data['text'] = [c.model_dump() for c in app.char_presses]
    return data


def play_char(app: App, c: CharPress) -> None:
    if (note := app.mapper(c.char)) is not None:
        if not app.silent:
            app.player.on_note(note, c.is_press)
        app.midi(note, c.is_press)
    if app.gui:
        app.main_window.on_char(c)


def clear_cached_values(app: App) -> None:
    keep = {
        'main_window',
        'listener',
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

    try:
        if app.output and app.silent:
            app.player.render_file(app.output, note_events(app), comment)
        else:
            if app.output:
                app.player.start_recording(app.output, comment)
            play_cli(app)
        completed = True
    finally:
        if not app.silent:
            app.player.stop_all()
            app.player.wait()
            if app.output:
                app.player.stop_recording()
            app.player.close()
        if app.output and not completed:
            app.output.unlink(missing_ok=True)


def note_events(app: App) -> list[tuple[int, NotePress]]:
    events: list[tuple[int, NotePress]] = []
    for press in app.char_presses:
        if (note := app.mapper(press.char)) is not None:
            frame = round(press.time * app.player.sample_rate / 1000)
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
