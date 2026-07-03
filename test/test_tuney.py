import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tuney.audio.mixer import NotePress
from tuney.audio.player import Player
from tuney.platform_info import exit_with_message, report_error
from tuney.time.char_press import CharPress
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney
from tuney.tuney_state import TuneyState
from tuney.ui import Action, State, StateChange


@contextmanager
def temporary_path() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory)


def on_transport_state(
    tuney: Tuney,
    old_state: State,
    state: State,
    action: Action,
    path: Path | None = None,
) -> bool:
    return tuney.state.audio_recorder.on_transport_state(
        StateChange(old_state=old_state, state=state, action=action),
        tuney.player,
        tuney.state._output_comment,
        path,
    )


def recorded_char_press(tuney: Tuney, c: CharPress) -> CharPress:
    return tuney.state.key_recorder.recorded_char_press(
        c, tuney.state.char_presses, tuney.max_gap
    )


def test_model_import_does_not_load_pyside() -> None:
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import sys; import tuney.tuney; print("PySide6" in sys.modules)',
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == 'False\n'


class FakeApp:
    is_replaying = False
    is_saving = False
    loop_replay = False
    loop_before = 0.0
    loop_after = 0.0
    loop_tempo = 1.0
    randomize_on_each_loop = False
    has_focus = True
    focus_in_control_panel = False

    def __init__(self) -> None:
        self.after_calls: list[tuple[str, int, object, tuple[object, ...]]] = []
        self.cancelled_after_ids: list[str] = []
        self.undo_count = 0
        self.history = self

    class layout:
        @staticmethod
        def set_text(_: str) -> None:
            pass

    ui = layout

    def checkpoint_undo(self) -> None:
        self.undo_count += 1

    @staticmethod
    def start() -> None:
        pass

    def after(self, delay: int, callback: object, *args: object) -> str:
        after_id = f'after-{len(self.after_calls)}'
        self.after_calls.append((after_id, delay, callback, args))
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self.cancelled_after_ids.append(after_id)

    @staticmethod
    def on_char(_: CharPress) -> None:
        pass

    @staticmethod
    def on_key(_: CharPress) -> None:
        pass


def test_recorded_char_press_uses_time_relative_to_first_key_press():
    tuney = Tuney()

    actual = [
        recorded_char_press(tuney, CharPress('a', time=1_700_000_000.0)),
        recorded_char_press(tuney, CharPress('a', False, 1_700_000_000.25)),
        recorded_char_press(tuney, CharPress('b', time=1_700_000_001.0)),
    ]

    assert actual == [
        CharPress('a', time=0.0),
        CharPress('a', False, 250.0),
        CharPress('b', time=1000.0),
    ]


def test_recorded_char_press_reuses_deleted_time_for_next_insert():
    tuney = Tuney()
    assert recorded_char_press(tuney, CharPress('a', time=100.0)) == CharPress(
        'a', time=0.0
    )
    tuney.state.key_recorder.insert_time = 0.0

    actual = [
        recorded_char_press(tuney, CharPress('b', time=110.0)),
        recorded_char_press(tuney, CharPress('b', False, 110.25)),
        recorded_char_press(tuney, CharPress('c', time=111.0)),
    ]

    assert actual == [
        CharPress('b', time=0.0),
        CharPress('b', False, 250.0),
        CharPress('c', time=1000.0),
    ]


def test_recorded_char_press_caps_silent_gap():
    tuney = Tuney(max_gap=0.5)
    for c in [
        CharPress('a', time=100.0),
        CharPress('a', False, 100.25),
    ]:
        tuney.state.append_char_press(recorded_char_press(tuney, c))

    actual = [
        recorded_char_press(tuney, CharPress('b', time=110.0)),
        recorded_char_press(tuney, CharPress('b', False, 110.25)),
    ]

    assert actual == [
        CharPress('b', time=750.0),
        CharPress('b', False, 1000.0),
    ]


def test_recorded_char_press_appends_to_restored_recording() -> None:
    tuney = Tuney(
        text=[
            CharPress('a', time=0.0),
            CharPress('a', False, 27123.0),
        ]
    )

    actual = [
        recorded_char_press(tuney, CharPress('t', time=100.0)),
        recorded_char_press(tuney, CharPress('t', False, 100.25)),
    ]

    assert actual == [
        CharPress('t', time=27123.0),
        CharPress('t', False, 27373.0),
    ]


def test_recorded_char_press_does_not_cap_time_while_note_is_held():
    tuney = Tuney(max_gap=0.5)
    tuney.state.append_char_press(
        recorded_char_press(tuney, CharPress('a', time=100.0))
    )

    actual = recorded_char_press(tuney, CharPress('b', time=110.0))

    assert actual == CharPress('b', time=10000.0)


def test_text_char_presses_must_be_sorted() -> None:
    with pytest.raises(ValueError, match='char_presses are not sorted by time'):
        Tuney(text=[CharPress('b', time=1000), CharPress('a', time=0)])


def test_append_char_press_sorts_late_char_press(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tuney = Tuney()

    tuney.state.append_char_press(CharPress('b', time=1000))
    tuney.state.append_char_press(CharPress('a', time=0))

    assert tuney.state.char_presses == [
        CharPress('a', time=0),
        CharPress('b', time=1000),
    ]
    assert 'Out-of-order char_press' in capsys.readouterr().err


def test_display_text_uses_only_key_presses():
    tuney = Tuney(
        text=[
            CharPress('a', time=0.0),
            CharPress('a', False, 250.0),
            CharPress('b', time=1000.0),
            CharPress('b', False, 1250.0),
        ]
    )

    assert tuney.state.display_text == 'ab'


def test_clear_resets_recording_state():
    tuney = Tuney(gui=True, text=[CharPress('a', time=0.0)])
    app = FakeApp()
    tuney.state.__dict__['app'] = app
    tuney.state.key_recorder.start_time = 100.0
    tuney.state.key_recorder.time_offset = 20.0
    tuney.state.key_recorder.insert_time = 10.0
    tuney.state.key_recorder.replay_text = 'a'

    tuney.state.clear()

    assert tuney.state.char_presses == []
    assert tuney.state.key_recorder.start_time is None
    assert tuney.state.key_recorder.time_offset == 0.0
    assert tuney.state.key_recorder.insert_time is None
    assert tuney.state.key_recorder.replay_text == ''
    assert app.undo_count == 1


def test_randomize_timing_replaces_timing_and_keeps_display_text() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 200.0),
            CharPress('b', time=10_000.0),
            CharPress('b', False, 10_500.0),
        ],
    )
    app = FakeApp()
    tuney.state.__dict__['app'] = app
    original_char_presses = list(tuney.state.char_presses)
    tuney.state.key_recorder.start_time = 100.0
    tuney.state.key_recorder.time_offset = 20.0
    tuney.state.key_recorder.insert_time = 10.0
    tuney.state.key_recorder.replay_text = 'a'

    tuney.state.randomize_timing()

    assert tuney.state.display_text == 'ab'
    assert tuney.state.char_presses != original_char_presses
    assert [c.char for c in tuney.state.char_presses if c.is_press] == ['a', 'b']
    assert tuney.state.key_recorder.start_time is None
    assert tuney.state.key_recorder.time_offset == 0.0
    assert tuney.state.key_recorder.insert_time is None
    assert tuney.state.key_recorder.replay_text == ''
    assert app.undo_count == 1


def test_text_file_loads_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('ab')
    tuney = Tuney(
        text_file=path,
        text_timings=TextTimings(seed=1, overlap=0, timings=[10]),
    )

    assert tuney.state.display_text == 'ab'
    assert [c.char for c in tuney.state.char_presses if c.is_press] == ['a', 'b']


def test_load_text_file_replaces_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('ab')
    tuney = Tuney(
        gui=True,
        text='old',
        text_timings=TextTimings(seed=1, overlap=0, timings=[10]),
    )
    app = FakeApp()
    tuney.state.__dict__['app'] = app
    tuney.state.key_recorder.start_time = 100.0

    tuney.state.load_text_file(path)

    assert tuney.state.display_text == 'ab'
    assert [c.char for c in tuney.state.char_presses if c.is_press] == ['a', 'b']
    assert tuney.state.key_recorder.start_time is None
    assert app.undo_count == 1


def test_on_char_records_undo_for_added_char_press() -> None:
    tuney = Tuney(gui=True, silent=True)
    app = FakeApp()
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('a', time=100.0))

    assert app.undo_count == 1


def test_gui_listener_queues_keys_through_app() -> None:
    tuney = Tuney(gui=True)
    app = FakeApp()
    tuney.state.__dict__['app'] = app

    assert tuney.state.listener.callback == app.on_key


def test_gui_start_uses_qt_keys_without_background_listener(monkeypatch) -> None:
    started = []
    tuney = Tuney(gui=True)
    app = FakeApp()
    tuney.state.__dict__['app'] = app
    monkeypatch.setattr(tuney.state.listener, 'start', lambda: started.append(True))

    tuney.state.start()

    assert started == []


def test_gui_start_uses_background_listener_when_enabled(monkeypatch) -> None:
    started = []
    tuney = Tuney(gui=True, run_in_background=True)
    app = FakeApp()
    tuney.state.__dict__['app'] = app
    monkeypatch.setattr(tuney.state.listener, 'start', lambda: started.append(True))

    tuney.state.start()

    assert started == [True]


def test_backspace_autorepeat_starts_after_configured_delay() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
        ],
        backspace_repeat_delay=1.5,
        backspace_repeat_rate=4.0,
    )
    app = FakeApp()
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('\b', time=200.0))

    assert tuney.state.display_text == 'a'
    assert app.after_calls[0][1] == 1500


def test_backspace_autorepeat_repeats_at_configured_rate() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
            CharPress('c', time=200.0),
        ],
        backspace_repeat_delay=2.0,
        backspace_repeat_rate=5.0,
    )
    app = FakeApp()
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('\b', time=300.0))
    first_callback = app.after_calls[0][2]
    assert callable(first_callback)
    first_callback()

    assert tuney.state.display_text == 'a'
    assert app.after_calls[1][1] == 200


def test_backspace_release_cancels_autorepeat() -> None:
    tuney = Tuney(gui=True, text=[CharPress('a', time=0.0)])
    app = FakeApp()
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('\b', time=100.0))
    tuney.state.on_char(CharPress('\b', False, time=200.0))

    assert app.cancelled_after_ids == ['after-0']
    assert tuney.state.key_recorder.backspace_repeat_after_id is None


def test_backspace_autorepeat_can_be_disabled() -> None:
    tuney = Tuney(
        gui=True,
        text=[CharPress('a', time=0.0)],
        backspace_repeat_rate=0,
    )
    app = FakeApp()
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('\b', time=100.0))

    assert app.after_calls == []


def test_restore_data_restores_char_presses_and_model_values() -> None:
    tuney = Tuney(max_gap=1.0, text=[CharPress('a', time=0)])

    tuney.state.restore_data(
        {'max_gap': 2.0, 'text': [CharPress('b', time=0).model_dump()]}
    )

    assert tuney.max_gap == 2.0
    assert tuney.state.char_presses == [CharPress('b', time=0)]


def test_autosave_path_uses_xdg_state_home(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        assert Tuney().state._autosave.path == tmp_path / 'tuney' / 'state.toml'


def test_frozen_errors_append_to_app_state_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        report_error('problem')

        log = tmp_path / 'tuney' / 'tuney.txt'
        assert 'problem' in log.read_text()


def test_frozen_text_exit_appends_to_app_state_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        with pytest.raises(SystemExit) as error:
            exit_with_message('fatal')

        assert error.value.code == 1
        log = tmp_path / 'tuney' / 'tuney.txt'
        assert 'fatal' in log.read_text()


def test_autosave_writes_current_model_without_app_state() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        tuney = Tuney(
            gui=True,
            max_gap=2.0,
            autosave_file=path,
            text=[
                CharPress('a', time=0),
                CharPress('a', False, 100),
            ],
        )

        tuney.state._autosave.save(tuney.state.save)

        data = tomllib.loads(path.read_text())
    assert data['gui']
    assert data['max_gap'] == 2.0
    assert data['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0},
        {'char': 'a', 'is_press': False, 'time': 100},
    ]
    assert 'autosave_file' not in data
    assert 'is_replaying' not in data
    assert 'loop_replay' not in data


def test_restore_autosave_restores_gui_state_without_explicit_startup_data() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        saved = Tuney(
            gui=True,
            max_gap=2.0,
            autosave_file=path,
            text=[
                CharPress('a', time=0),
                CharPress('a', False, 100),
            ],
        )
        saved.state._autosave.save(saved.state.save)
        tuney = Tuney(gui=True, autosave_file=path)

        tuney.state._autosave.restore(tuney)

        assert tuney.max_gap == 2.0
        assert tuney.state.char_presses == [
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ]
        assert tuney.autosave_file == path


def test_restore_autosave_ignores_invalid_state_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        path.write_text('max_gap =')
        tuney = Tuney(gui=True, autosave_file=path)

        tuney.state._autosave.restore(tuney)

        assert tuney.max_gap == Tuney().max_gap
    assert f'Could not restore {path}' in capsys.readouterr().err


def test_restore_autosave_defaults_invalid_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        path.write_text('max_gap = "bad"\nhover_time = 2.0\n')
        tuney = Tuney(gui=True, autosave_file=path)

        tuney.state._autosave.restore(tuney)

        assert tuney.max_gap == Tuney().max_gap
        assert tuney.hover_time == 2.0
    error = capsys.readouterr().err
    assert f'Could not restore fields from {path}' in error
    assert 'max_gap' in error


def test_restore_autosave_defaults_invalid_nested_scale(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        path.write_text(
            '\n'.join(
                [
                    'hover_time = 2.0',
                    '[player.scale]',
                    'note_names = "AB"',
                    'root = "C"',
                    'begin = "A"',
                    'end = "B"',
                ]
            )
        )
        tuney = Tuney(gui=True, autosave_file=path)

        tuney.state._autosave.restore(tuney)

        assert tuney.hover_time == 2.0
        assert tuney.player.scale == Tuney().player.scale
    error = capsys.readouterr().err
    assert f'Could not restore fields from {path}' in error
    assert 'root must be present in note_names' in error


def test_restore_autosave_does_not_override_explicit_text() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        saved = Tuney(gui=True, autosave_file=path, text=[CharPress('a', time=0)])
        saved.state._autosave.save(saved.state.save)
        tuney = Tuney(gui=True, autosave_file=path, text='b')

        tuney.state._autosave.restore(tuney)

        assert tuney.state.display_text == 'b'


def test_finished_replay_restarts_when_looping(monkeypatch) -> None:
    calls: list[str] = []
    tuney = Tuney(gui=True, text=[CharPress('a', time=0)])
    app = FakeApp()
    app.is_replaying = True
    app.loop_replay = True
    tuney.state.__dict__['app'] = app
    monkeypatch.setattr(TuneyState, 'on_replay', lambda self: calls.append('replay'))

    tuney.state.key_recorder.finish_replay(tuney.state)

    assert calls == ['replay']
    assert app.is_replaying


def test_finished_empty_replay_stops_when_looping() -> None:
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.is_replaying = True
    app.loop_replay = True
    tuney.state.__dict__['app'] = app

    tuney.state.key_recorder.finish_replay(tuney.state)

    assert not app.is_replaying


def test_replay_char_presses_use_loop_tempo() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 1000),
        ],
    )
    app = FakeApp()
    app.loop_tempo = 2.0
    tuney.state.__dict__['app'] = app

    assert tuney.state._replay_char_presses() == [
        CharPress('a', time=0),
        CharPress('a', False, 500),
    ]


def test_replay_char_presses_cut_loop_start_and_end() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
            CharPress('b', time=1000),
            CharPress('b', False, 1500),
        ],
    )
    app = FakeApp()
    app.loop_before = 0.5
    app.loop_after = 0.25
    tuney.state.__dict__['app'] = app

    assert tuney.state._replay_char_presses() == [
        CharPress('a', False, 0),
        CharPress('b', time=500),
    ]


def test_replay_char_presses_add_loop_start_and_end_space() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
        ],
    )
    app = FakeApp()
    app.loop_before = -0.25
    app.loop_after = -0.75
    tuney.state.__dict__['app'] = app

    assert tuney.state._replay_char_presses() == [
        CharPress('a', time=250),
        CharPress('a', False, 750),
        CharPress(time=1500),
    ]


def test_loop_randomize_replaces_playback_timing_without_changing_recording() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
            CharPress('b', time=10_000),
            CharPress('b', False, 11_000),
            CharPress('c', time=20_000),
            CharPress('c', False, 21_000),
            CharPress('d', time=30_000),
            CharPress('d', False, 31_000),
        ],
        text_timings=TextTimings(seed=1, overlap=0, timings=[10, 20, 30]),
    )
    app = FakeApp()
    app.loop_replay = True
    app.randomize_on_each_loop = True
    tuney.state.__dict__['app'] = app
    recorded_char_presses = list(tuney.state.char_presses)

    first_loop = tuney.state._replay_char_presses()
    second_loop = tuney.state._replay_char_presses()

    assert tuney.state.char_presses == recorded_char_presses
    assert first_loop != recorded_char_presses
    assert second_loop != first_loop
    assert ''.join(c.char for c in first_loop if c.is_press) == 'abcd'
    assert ''.join(c.char for c in second_loop if c.is_press) == 'abcd'


def test_randomize_on_each_loop_only_affects_loop_replay() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
        text_timings=TextTimings(seed=1, overlap=0, timings=[10, 20, 30]),
    )
    app = FakeApp()
    app.randomize_on_each_loop = True
    tuney.state.__dict__['app'] = app

    assert tuney.state._replay_char_presses() == tuney.state.char_presses


def test_on_char_ignores_input_while_saving():
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.is_saving = True
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('a', time=100.0))

    assert tuney.state.char_presses == []


def test_on_char_ignores_input_without_app_focus():
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.has_focus = False
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('a', time=100.0))

    assert tuney.state.char_presses == []


def test_on_char_ignores_input_with_control_panel_focus():
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.focus_in_control_panel = True
    tuney.state.__dict__['app'] = app

    tuney.state.on_char(CharPress('a', time=100.0))

    assert tuney.state.char_presses == []


def test_cli_mode_plays_recorded_events_without_gui(monkeypatch) -> None:
    events: list[tuple[int, bool]] = []
    lifecycle: list[str] = []
    monkeypatch.setattr(
        Player,
        'on_note',
        lambda self, note, is_press: events.append((note, is_press)) or True,
    )
    monkeypatch.setattr(Player, 'stop_all', lambda self: lifecycle.append('stop_all'))
    monkeypatch.setattr(Player, 'wait', lambda self: lifecycle.append('wait'))
    monkeypatch.setattr(Player, 'close', lambda self: lifecycle.append('close'))
    tuney = Tuney(
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )

    tuney.state()

    assert events == [(-6, True), (-6, False)]
    assert lifecycle == ['stop_all', 'wait', 'close']
    assert 'app' not in tuney.state.__dict__
    assert 'listener' not in tuney.state.__dict__


def test_cli_mode_prints_characters_as_they_play(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    printed: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(Player, 'on_note', lambda *args: True)
    monkeypatch.setattr(
        'builtins.print',
        lambda *args, **kwargs: printed.append((args, kwargs)),
    )
    tuney = Tuney(
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
            CharPress('b', time=0),
            CharPress('b', False, 0),
        ],
    )

    tuney.state._play_cli()

    assert printed == [
        (('a',), {'end': '', 'flush': True}),
        (('b',), {'end': '', 'flush': True}),
        ((), {}),
    ]


def test_cli_mode_prints_newline_before_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt(*args: object) -> bool:
        raise KeyboardInterrupt

    printed: list[tuple[tuple[object, ...], dict[str, object]]] = []
    interrupted = False
    monkeypatch.setattr(
        'builtins.print',
        lambda *args, **kwargs: printed.append((args, kwargs)),
    )
    monkeypatch.setattr(Player, 'on_note', interrupt)
    tuney = Tuney(text=[CharPress('a', time=0)])
    try:
        tuney.state._play_cli()
    except KeyboardInterrupt:
        interrupted = True

    assert interrupted
    assert printed == [
        (('a',), {'end': '', 'flush': True}),
        ((), {}),
    ]


def test_cli_mode_requires_text(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        Tuney().state()

    error = capsys.readouterr().err
    assert exc_info.value.code == 2
    assert 'Required options were not provided: TEXT' in error
    assert 'For full helptext, run tuney --help' in error


def test_cli_mode_requires_sound() -> None:
    with pytest.raises(SystemExit, match='CLI mode requires sound'):
        Tuney(silent=True, text='a').state()


def test_output_forces_cli_mode() -> None:
    tuney = Tuney(gui=True, output=Path('out.wav'))

    assert not tuney.gui


def test_silent_cli_mode_writes_audio_file(monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path('out.wav')
    rendered: list[
        tuple[Path, list[tuple[int, NotePress]], Callable[[], str] | None]
    ] = []

    def render_file(
        self: Player,
        output: Path,
        events: list[tuple[int, NotePress]],
        comment: Callable[[], str] | None = None,
    ) -> None:
        rendered.append((output, events, comment))

    monkeypatch.setattr(Player, 'render_file', render_file)
    tuney = Tuney(
        output=path,
        silent=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
    )

    tuney.state()
    output, events, comment = rendered[0]

    assert output == path
    assert [(frame, note.is_press) for frame, note in events] == [
        (0, True),
        (4800, False),
    ]
    assert callable(comment)


def test_live_cli_output_records_during_playback(monkeypatch) -> None:
    path = Path('out.wav')
    lifecycle: list[object] = []
    monkeypatch.setattr(Player, 'on_note', lambda *args: True)
    monkeypatch.setattr(
        Player,
        'start_recording',
        lambda self, output, comment=None: lifecycle.append(
            ('start_recording', output, comment)
        ),
    )
    monkeypatch.setattr(Player, 'stop_all', lambda self: lifecycle.append('stop_all'))
    monkeypatch.setattr(Player, 'wait', lambda self: lifecycle.append('wait'))
    monkeypatch.setattr(
        Player,
        'stop_recording',
        lambda self: lifecycle.append('stop_recording'),
    )
    monkeypatch.setattr(Player, 'close', lambda self: lifecycle.append('close'))
    monkeypatch.setattr(
        TuneyState, '_play_cli', lambda self: lifecycle.append('play_cli')
    )
    tuney = Tuney(
        output=path,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )
    tuney.state()

    start_recording, play_cli, stop_all, wait, stop_recording, close = lifecycle
    assert start_recording[0] == 'start_recording'
    assert start_recording[1] == path
    assert callable(start_recording[2])
    assert [
        play_cli,
        stop_all,
        wait,
        stop_recording,
        close,
    ] == [
        'play_cli',
        'stop_all',
        'wait',
        'stop_recording',
        'close',
    ]


def test_interrupted_output_removes_partial_file(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'out.wav'

        def interrupt(self, output, events, comment=None) -> None:
            output.write_bytes(b'partial')
            raise KeyboardInterrupt

        monkeypatch.setattr(Player, 'render_file', interrupt)
        tuney = Tuney(output=path, silent=True, text='a')

        with pytest.raises(KeyboardInterrupt):
            tuney.state()

        assert not path.exists()


def test_gui_transport_records_audio_until_save(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        output = tmp_path / 'out.wav'
        lifecycle: list[object] = []

        def start_recording(
            self,
            path: Path,
            comment: object | None = None,
            append: bool = False,
        ) -> None:
            lifecycle.append(('start_recording', path, comment, append))

        monkeypatch.setattr(Player, 'start_recording', start_recording)
        monkeypatch.setattr(
            Player,
            'stop_recording',
            lambda self: lifecycle.append('stop_recording'),
        )
        tuney = Tuney(gui=True)
        assert on_transport_state(tuney, State.ready, State.recording, Action.record)
        comment = tuney.state.audio_recorder.comment
        assert on_transport_state(tuney, State.recording, State.paused, Action.record)
        assert on_transport_state(tuney, State.paused, State.recording, Action.record)
        assert on_transport_state(
            tuney, State.recording, State.ready, Action.save, output
        )

        first_start, stop, second_start, stop_before_save = lifecycle
        assert first_start[0] == 'start_recording'
        assert first_start[2] is comment
        assert first_start[3] is False
        assert stop == 'stop_recording'
        assert second_start[0] == 'start_recording'
        assert second_start[1] == first_start[1]
        assert second_start[2] is comment
        assert second_start[3] is True
        assert stop_before_save == 'stop_recording'
        assert output.exists()
        assert tuney.state.audio_recorder.path is None
        assert tuney.state.audio_recorder.comment is None


def test_gui_transport_cancel_keeps_audio_recording(monkeypatch) -> None:
    lifecycle: list[object] = []
    monkeypatch.setattr(
        Player,
        'start_recording',
        lambda self, path, comment=None, append=False: lifecycle.append(
            ('start_recording', path, comment, append)
        ),
    )
    monkeypatch.setattr(
        Player, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    tuney = Tuney(gui=True)

    assert on_transport_state(tuney, State.ready, State.recording, Action.record)
    recording_path = tuney.state.audio_recorder.path

    assert not on_transport_state(tuney, State.recording, State.ready, Action.save)
    assert tuney.state.audio_recorder.path == recording_path
    assert lifecycle[0][0] == 'start_recording'
    assert lifecycle == [lifecycle[0]]
    if recording_path is not None:
        recording_path.unlink(missing_ok=True)


def test_gui_transport_clear_discards_audio_recording(monkeypatch) -> None:
    lifecycle: list[object] = []
    monkeypatch.setattr(
        Player,
        'start_recording',
        lambda self, path, comment=None, append=False: lifecycle.append(
            ('start_recording', path, comment, append)
        ),
    )
    monkeypatch.setattr(
        Player, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    tuney = Tuney(gui=True)

    assert on_transport_state(tuney, State.ready, State.recording, Action.record)
    recording_path = tuney.state.audio_recorder.path
    assert recording_path is not None

    assert on_transport_state(tuney, State.recording, State.ready, Action.clear)

    assert lifecycle[0][0] == 'start_recording'
    assert lifecycle[1] == 'stop_recording'
    assert not recording_path.exists()
    assert tuney.state.audio_recorder.path is None
    assert tuney.state.audio_recorder.comment is None
