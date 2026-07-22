import os
import random
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from queue import SimpleQueue
from urllib.parse import parse_qs, urlparse

import mido
import pytest

import tuney.app.app
import tuney.app.platform_info
from tuney.app.app import (
    App,
    append_char_press,
    clear,
    load_text_file,
    on_char,
    output_comment,
    play_cli,
    randomize_settings,
    randomize_timing,
    replay_char_presses,
    restore_data,
    run,
    save,
    start,
)
from tuney.app.global_config import GlobalConfig
from tuney.app.platform_info import (
    APP_USER_MODEL_ID,
    ISSUE_URL,
    acquire_single_instance,
    crash_issue_url,
    crash_marker_path,
    error_issue_url,
    exit_with_message,
    instance_lock_path,
    instrument,
    mark_session_clean_exit,
    mark_session_started,
    problem_issue_url,
    release_single_instance,
    report_error,
    set_windows_app_user_model_id,
    trace,
)
from tuney.app.runnable import start_thread
from tuney.app.text_timing import edit_text_timing
from tuney.audio.mixer import NotePress
from tuney.audio.player import Player
from tuney.scale.tuning import Computed, Type
from tuney.time.char_press import CharPress
from tuney.time.sequencer import Sequencer
from tuney.time.text_timings import TextTimings
from tuney.ui import Action, State, StateChange, startup
from tuney.ui.history import History
from tuney.ui.main_window import MainWindow


@contextmanager
def temporary_path() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory)


def on_transport_state(
    app: App,
    old_state: State,
    state: State,
    action: Action,
    path: Path | None = None,
) -> bool:
    return app.audio_recorder.on_transport_state(
        StateChange(old_state=old_state, state=state, action=action),
        app.player,
        lambda: output_comment(app),
        path,
    )


def recorded_char_press(app: App, c: CharPress) -> CharPress:
    return app.key_recorder.recorded_char_press(c, app.char_presses, app.max_gap)


def set_autosave_file(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(startup, 'autosave_file', path)


def test_model_import_does_not_load_pyside() -> None:
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import sys; import tuney.config.tuney; print("PySide6" in sys.modules)',
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == 'False\n'


def test_error_issue_url_includes_traceback() -> None:
    path = Path('/tmp/tuney.txt')
    try:
        raise RuntimeError('broken saved state')
    except RuntimeError as error:
        url = error_issue_url(error, path)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert f'{parsed.scheme}://{parsed.netloc}{parsed.path}' == ISSUE_URL
    assert query['title'] == ['RuntimeError: broken saved state']
    body = query['body'][0]
    assert 'RuntimeError: broken saved state' in body
    assert f'Log file: {path}' in body
    assert 'Traceback (most recent call last)' in body


def test_crash_issue_url_includes_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        log = tmp_path / 'tuney' / 'tuney.txt'
        log.parent.mkdir(parents=True)
        log.write_text('TRACE one\nTRACE two\n')

        url = crash_issue_url(log)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f'{parsed.scheme}://{parsed.netloc}{parsed.path}' == ISSUE_URL
    assert query['title'] == ['Tuney crashed']
    body = query['body'][0]
    assert 'Tuney appears to have crashed during the previous run.' in body
    assert 'TRACE one\nTRACE two' in body


def test_problem_issue_url_includes_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        log = tmp_path / 'tuney' / 'tuney.txt'
        log.parent.mkdir(parents=True)
        log.write_text('TRACE problem\n')

        url = problem_issue_url(log)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f'{parsed.scheme}://{parsed.netloc}{parsed.path}' == ISSUE_URL
    assert query['title'] == ['Tuney problem report']
    body = query['body'][0]
    assert 'Problem report from Tuney.' in body
    assert 'TRACE problem' in body


def test_app_user_model_id_is_windows_only(monkeypatch) -> None:
    calls = []

    class Shell32:
        @staticmethod
        def SetCurrentProcessExplicitAppUserModelID(app_id: str) -> int:
            calls.append(app_id)
            return 0

    class Windll:
        shell32 = Shell32()

    monkeypatch.setattr('tuney.app.platform_info.sys.platform', 'darwin')
    monkeypatch.setattr(
        'tuney.app.platform_info.ctypes.windll', Windll(), raising=False
    )

    set_windows_app_user_model_id()

    assert calls == []


def test_app_user_model_id_is_set_on_windows(monkeypatch) -> None:
    calls = []

    class Shell32:
        @staticmethod
        def SetCurrentProcessExplicitAppUserModelID(app_id: str) -> int:
            calls.append(app_id)
            return 0

    class Windll:
        shell32 = Shell32()

    monkeypatch.setattr('tuney.app.platform_info.sys.platform', 'win32')
    monkeypatch.setattr(
        'tuney.app.platform_info.ctypes.windll', Windll(), raising=False
    )

    set_windows_app_user_model_id()

    assert calls == [APP_USER_MODEL_ID]


def test_windows_process_check_uses_untruncated_handle(monkeypatch) -> None:
    handle = 0x123456789
    calls = []

    class Kernel32:
        @staticmethod
        def OpenProcess(access: int, inherit: bool, pid: int) -> int:
            calls.append(('open', access, inherit, pid))
            return handle

        @staticmethod
        def GetExitCodeProcess(process: int, exit_code: object) -> int:
            calls.append(('exit', process))
            exit_code._obj.value = 259
            return 1

        @staticmethod
        def CloseHandle(process: int) -> int:
            calls.append(('close', process))
            return 1

    class Windll:
        kernel32 = Kernel32()

    monkeypatch.setattr(
        'tuney.app.platform_info.ctypes.windll', Windll(), raising=False
    )

    assert tuney.app.platform_info._windows_process_is_alive(1234)
    assert calls == [
        ('open', 0x1000, False, 1234),
        ('exit', handle),
        ('close', handle),
    ]


def test_audio_diagnostics_use_reportable_dialog() -> None:
    from tuney.ui.main_window import MainWindow

    class FakeDiagnostics:
        def take_errors(self) -> list[str]:
            return ['cannot render block']

    class FakeEngine:
        diagnostics = FakeDiagnostics()

    class FakePlayer:
        def __init__(self) -> None:
            self.engine = FakeEngine()

    class FakeApp:
        player = FakePlayer()

    class FakeWindow:
        key_queue = SimpleQueue()
        queue = SimpleQueue()
        app = FakeApp()
        errors: list[str] = []

        def _on_char(self, c: CharPress) -> None:
            raise AssertionError(c)

        def show_audio_error(self, error: str) -> None:
            self.errors.append(error)

    window = FakeWindow()

    MainWindow._handle_queue(window)

    assert window.errors == ['cannot render block']


def test_crash_marker_tracks_unclean_shutdown(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        assert not mark_session_started()
        assert not mark_session_started()
        crash_marker_path().write_text('123456')
        monkeypatch.setattr(
            'tuney.app.platform_info._process_is_alive', lambda _: False
        )
        assert mark_session_started()
        mark_session_clean_exit()
        assert not mark_session_started()


def test_crash_marker_clean_exit_only_removes_current_process(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        crash_marker_path().parent.mkdir(parents=True)
        crash_marker_path().write_text('123456')

        mark_session_clean_exit()

        assert crash_marker_path().exists()


def test_single_instance_lock_blocks_second_instance(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        instance_lock_path().parent.mkdir(parents=True)
        instance_lock_path().write_text(str(os.getpid()))

        assert not acquire_single_instance()
        instance_lock_path().unlink()
        assert acquire_single_instance()
        release_single_instance()


def test_single_instance_lock_replaces_stale_lock(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        instance_lock_path().parent.mkdir(parents=True)
        instance_lock_path().write_text('123456')
        monkeypatch.setattr(
            'tuney.app.platform_info._process_is_alive', lambda _: False
        )

        assert acquire_single_instance()
        release_single_instance()


def test_gui_run_exits_when_another_instance_is_running(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        calls: list[str] = []
        instance_lock_path().parent.mkdir(parents=True)
        instance_lock_path().write_text(str(os.getpid()))

        class Autosave:
            @staticmethod
            def restore(_: object) -> None:
                calls.append('restore')

        class FakeWindow:
            @staticmethod
            def mainloop() -> None:
                calls.append('mainloop')

        class FakeApp:
            gui = True
            _autosave = Autosave()
            main_window = FakeWindow()

        monkeypatch.setattr(
            tuney.app.app, 'show_already_running', lambda: calls.append('busy')
        )

        run(FakeApp())

        assert calls == ['busy']


def test_run_restores_autosave_before_constructing_window_and_continues(
    monkeypatch,
) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        calls: list[str] = []

        class FailingAutosave:
            @staticmethod
            def restore(_: object) -> RuntimeError:
                calls.append('restore')
                return RuntimeError('broken saved state')

        class FakeWindow:
            error: BaseException | None = None

            def show_restore_error(self, error: BaseException) -> None:
                calls.append('error')
                self.error = error

            @staticmethod
            def mainloop() -> None:
                calls.append('mainloop')

        window = FakeWindow()

        class FakeApp:
            gui = True
            _autosave = FailingAutosave()

            @property
            def main_window(self) -> FakeWindow:
                calls.append('window')
                return window

        app = FakeApp()
        monkeypatch.setattr(tuney.app.app, 'start', lambda _: None)

        run(app)

        assert isinstance(window.error, RuntimeError)
        assert calls == ['restore', 'window', 'error', 'mainloop']


def test_run_reports_previous_frozen_crash(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        crash_marker_path().parent.mkdir(parents=True)
        crash_marker_path().write_text('123456')
        calls: list[str] = []

        class Autosave:
            @staticmethod
            def restore(_: object) -> None:
                calls.append('restore')

        class FakeWindow:
            @staticmethod
            def show_crash_report() -> None:
                calls.append('crash')

            @staticmethod
            def mainloop() -> None:
                calls.append('mainloop')

        class FakeApp:
            gui = True
            _autosave = Autosave()
            main_window = FakeWindow()

        monkeypatch.setattr(tuney.app.app, 'is_frozen', lambda: True)
        monkeypatch.setattr(
            'tuney.app.platform_info._process_is_alive', lambda _: False
        )
        monkeypatch.setattr(tuney.app.app, 'start', lambda _: None)

        run(FakeApp())

        assert calls == ['restore', 'crash', 'mainloop']
        assert not crash_marker_path().exists()


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

        @staticmethod
        def set_text_timings(_: list[list[str]]) -> None:
            pass

        @staticmethod
        def rebuild_control_panel() -> None:
            pass

        @staticmethod
        def rebuild_note_grid() -> None:
            pass

        @staticmethod
        def set_play_cursor(_: int | None) -> None:
            pass

        @staticmethod
        def set_active_text_timing(_: int | None) -> None:
            pass

    ui = layout

    def update_text_display(self) -> None:
        pass

    def sync_config_actions(self) -> None:
        pass

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
    app = App()

    actual = [
        recorded_char_press(app, CharPress('a', time=1_700_000_000.0)),
        recorded_char_press(app, CharPress('a', False, 1_700_000_000.25)),
        recorded_char_press(app, CharPress('b', time=1_700_000_001.0)),
    ]

    assert actual == [
        CharPress('a', time=0.0),
        CharPress('a', False, 250.0),
        CharPress('b', time=1000.0),
    ]


def test_recorded_char_press_reuses_deleted_time_for_next_insert():
    app = App()
    assert recorded_char_press(app, CharPress('a', time=100.0)) == CharPress(
        'a', time=0.0
    )
    app.key_recorder.insert_time = 0.0

    actual = [
        recorded_char_press(app, CharPress('b', time=110.0)),
        recorded_char_press(app, CharPress('b', False, 110.25)),
        recorded_char_press(app, CharPress('c', time=111.0)),
    ]

    assert actual == [
        CharPress('b', time=0.0),
        CharPress('b', False, 250.0),
        CharPress('c', time=1000.0),
    ]


def test_recorded_char_press_caps_silent_gap():
    app = App(max_gap=0.5)
    for c in [
        CharPress('a', time=100.0),
        CharPress('a', False, 100.25),
    ]:
        append_char_press(app, recorded_char_press(app, c))

    actual = [
        recorded_char_press(app, CharPress('b', time=110.0)),
        recorded_char_press(app, CharPress('b', False, 110.25)),
    ]

    assert actual == [
        CharPress('b', time=750.0),
        CharPress('b', False, 1000.0),
    ]


def test_recorded_char_press_appends_to_restored_recording() -> None:
    app = App(
        text=[
            CharPress('a', time=0.0),
            CharPress('a', False, 27123.0),
        ]
    )

    actual = [
        recorded_char_press(app, CharPress('t', time=100.0)),
        recorded_char_press(app, CharPress('t', False, 100.25)),
    ]

    assert actual == [
        CharPress('t', time=27123.0),
        CharPress('t', False, 27373.0),
    ]


def test_recorded_char_press_does_not_cap_time_while_note_is_held():
    app = App(max_gap=0.5)
    append_char_press(app, recorded_char_press(app, CharPress('a', time=100.0)))

    actual = recorded_char_press(app, CharPress('b', time=110.0))

    assert actual == CharPress('b', time=10000.0)


def test_text_char_presses_must_be_sorted() -> None:
    with pytest.raises(ValueError, match='char_presses are not sorted by time'):
        App(text=[CharPress('b', time=1000), CharPress('a', time=0)])


def test_append_char_press_sorts_late_char_press(
    capsys,
) -> None:
    app = App()

    append_char_press(app, CharPress('b', time=1000))
    append_char_press(app, CharPress('a', time=0))

    assert app.char_presses == [
        CharPress('a', time=0),
        CharPress('b', time=1000),
    ]
    assert 'Out-of-order char_press' in capsys.readouterr().err


def test_display_text_uses_only_key_presses():
    app = App(
        text=[
            CharPress('a', time=0.0),
            CharPress('a', False, 250.0),
            CharPress('b', time=1000.0),
            CharPress('b', False, 1250.0),
        ]
    )

    assert app.display_text == 'ab'


def test_display_text_timings_show_offsets() -> None:
    app = App(
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 250.0),
            CharPress('\b', time=300.0),
        ]
    )

    assert app.display_text_timings == [
        ['a', '100', '150'],
        ['\b', '200', ''],
    ]


def test_edit_text_timings_updates_char_presses() -> None:
    app = App(
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 250.0),
            CharPress('b', time=300.0),
        ]
    )

    edit_text_timing(app.char_presses, 0, 0, 'c')
    edit_text_timing(app.char_presses, 1, 1, '500')
    edit_text_timing(app.char_presses, 1, 2, '75')

    assert app.char_presses == [
        CharPress('c', time=100.0),
        CharPress('c', False, 250.0),
        CharPress('b', time=600.0),
        CharPress('b', False, 675.0),
    ]


def test_char_press_negative_time_is_zero() -> None:
    assert CharPress('a', time=-1).time == 0.0


def test_clear_resets_recording_state():
    app = App(gui=True, text=[CharPress('a', time=0.0)], max_gap=2.0)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    app.key_recorder.start_time = 100.0
    app.key_recorder.time_offset = 20.0
    app.key_recorder.insert_time = 10.0
    app.key_recorder.replay_text = 'a'

    clear(app)

    assert app.char_presses == []
    assert app.max_gap == App().max_gap
    assert app.key_recorder.start_time is None
    assert app.key_recorder.time_offset == 0.0
    assert app.key_recorder.insert_time is None
    assert app.key_recorder.replay_text == ''
    assert main_window.undo_count == 1


def test_randomize_timing_replaces_timing_and_keeps_display_text() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 200.0),
            CharPress('b', time=10_000.0),
            CharPress('b', False, 10_500.0),
        ],
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    original_char_presses = list(app.char_presses)
    app.key_recorder.start_time = 100.0
    app.key_recorder.time_offset = 20.0
    app.key_recorder.insert_time = 10.0
    app.key_recorder.replay_text = 'a'

    randomize_timing(app)

    assert app.display_text == 'ab'
    assert app.char_presses != original_char_presses
    assert [c.char for c in app.char_presses if c.is_press] == ['a', 'b']
    assert app.key_recorder.start_time is None
    assert app.key_recorder.time_offset == 0.0
    assert app.key_recorder.insert_time is None
    assert app.key_recorder.replay_text == ''
    assert main_window.undo_count == 1


def test_randomize_settings_changes_valid_scale_and_tuning_only() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 200.0),
        ],
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    text_timings = app.text_timings.model_copy(deep=True)
    char_presses = list(app.char_presses)

    randomize_settings(app, random.Random(1))

    assert type(app).model_validate(app.model_dump())
    assert app.text_timings == text_timings
    assert app.char_presses == char_presses
    assert app.tuning.type == Type.computed
    assert isinstance(app.tuning.computed, Computed)
    assert app.tuning.computed.notes_per_octave == sum(app.scale.intervals)
    assert 5 <= app.tuning.computed.notes_per_octave <= 12
    assert 220 <= app.tuning.root_frequency <= 660
    assert 48 <= app.tuning.root_note <= 72
    assert app.scale.begin == 'A'
    assert app.scale.end == 'G'
    assert app.scale.root in 'ABCDEFG'
    assert main_window.undo_count == 1


def test_text_file_loads_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('ab')
    app = App(
        text_file=path,
        text_timings=TextTimings(seed=1, overlap=0, timings=[10]),
    )

    assert app.display_text == 'ab'
    assert [c.char for c in app.char_presses if c.is_press] == ['a', 'b']


def test_text_file_loads_non_utf8_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_bytes('café'.encode('cp1252'))
    app = App(
        text_file=path,
        text_timings=TextTimings(seed=1, overlap=0, strip_accents=False, timings=[10]),
    )

    assert app.display_text == 'café'


def test_load_text_file_replaces_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('ab')
    app = App(
        gui=True,
        text='old',
        text_timings=TextTimings(seed=1, overlap=0, timings=[10]),
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    app.key_recorder.start_time = 100.0

    load_text_file(app, path)

    assert app.display_text == 'ab'
    assert [c.char for c in app.char_presses if c.is_press] == ['a', 'b']
    assert app.key_recorder.start_time is None
    assert main_window.undo_count == 1


def test_on_char_records_undo_for_added_char_press() -> None:
    app = App(gui=True, silent=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('a', time=100.0))

    assert main_window.undo_count == 1


def test_history_checkpoint_ignores_live_sequencer() -> None:
    class FakeWindow:
        def __init__(self) -> None:
            self.app = App(gui=True, text='a')

    window = FakeWindow()
    history = History(window)
    window.app.key_recorder.sequencer = Sequencer(
        char_presses=[CharPress('a', time=60_000)],
        callback=lambda _: None,
    )

    history.checkpoint_undo()

    assert len(history.undo_stack) == 1
    assert history.undo_stack[0].key_recorder.sequencer is None


def test_randomize_on_each_loop_ignores_live_sequencer() -> None:
    class FakeWindow:
        def __init__(self) -> None:
            self.app = App(gui=True, text='a')
            self.history = History(self)

    window = FakeWindow()
    window.app.key_recorder.sequencer = Sequencer(
        char_presses=[CharPress('a', time=60_000)],
        callback=lambda _: None,
    )

    MainWindow.on_randomize_on_each_loop(window, True)

    assert window.history.randomize_on_each_loop


def test_gui_listener_queues_keys_through_app() -> None:
    app = App(gui=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    assert app.keyboard_listener.callback == main_window.on_key


def test_gui_start_uses_qt_keys_without_background_listener(monkeypatch) -> None:
    started = []
    app = App(gui=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    monkeypatch.setattr(app.keyboard_listener, 'start', lambda: started.append(True))

    start(app)

    assert started == []


def test_gui_start_uses_background_listener_when_enabled(monkeypatch) -> None:
    started = []
    app = App(gui=True, run_in_background=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    monkeypatch.setattr(app.keyboard_listener, 'start', lambda: started.append(True))

    start(app)

    assert started == [True]


def test_backspace_autorepeat_starts_after_configured_delay() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
        ],
        backspace_repeat_delay=1.5,
        backspace_repeat_rate=4.0,
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('\b', time=200.0))

    assert app.display_text == 'a'
    assert main_window.after_calls[0][1] == 1500


def test_backspace_autorepeat_repeats_at_configured_rate() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
            CharPress('c', time=200.0),
        ],
        backspace_repeat_delay=2.0,
        backspace_repeat_rate=5.0,
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('\b', time=300.0))
    first_callback = main_window.after_calls[0][2]
    assert callable(first_callback)
    first_callback()

    assert app.display_text == 'a'
    assert main_window.after_calls[1][1] == 200


def test_backspace_release_cancels_autorepeat() -> None:
    app = App(gui=True, text=[CharPress('a', time=0.0)])
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('\b', time=100.0))
    on_char(app, CharPress('\b', False, time=200.0))

    assert main_window.cancelled_after_ids == ['after-0']
    assert app.key_recorder.backspace_repeat_after_id is None


def test_backspace_autorepeat_can_be_disabled() -> None:
    app = App(
        gui=True,
        text=[CharPress('a', time=0.0)],
        backspace_repeat_rate=0,
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('\b', time=100.0))

    assert main_window.after_calls == []


def test_restore_data_restores_char_presses_and_model_values() -> None:
    app = App(max_gap=1.0, text=[CharPress('a', time=0)])

    restore_data(
        app,
        {'max_gap': 2.0, 'text': [CharPress('b', time=0).model_dump()]},
    )

    assert app.max_gap == 2.0
    assert app.char_presses == [CharPress('b', time=0)]


def test_restore_data_closes_cached_player(monkeypatch) -> None:
    app = App()
    player = app.player
    closed: list[Player] = []
    monkeypatch.setattr(Player, 'close', lambda self: closed.append(self))

    restore_data(app, {'max_gap': 2.0})

    assert closed == [player]
    assert 'player' not in app.__dict__


def test_autosave_path_uses_xdg_state_home(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        assert App()._autosave.path == tmp_path / 'tuney' / 'state.toml'


def test_global_config_persists_dialog_directories() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        config = GlobalConfig(file=path)

        config.remember_directory('Open Text File', str(tmp_path / 'texts' / 'a.txt'))

        assert GlobalConfig.read(path).directories == {
            'Open Text File': str(tmp_path / 'texts')
        }


def test_global_config_persists_buffer_size() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        config = GlobalConfig(file=path)

        assert config.buffer_size == 32
        assert config.increase_buffer_size() == 64
        assert GlobalConfig.read(path).buffer_size == 64


def test_global_config_persists_control_panel_state() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        config = GlobalConfig(file=path)
        config.control_panel_sections['Tuney.sound'] = False
        config.control_panel_scroll = 120

        config.save()

        saved = GlobalConfig.read(path)
        assert saved.control_panel_sections == {'Tuney.sound': False}
        assert saved.control_panel_scroll == 120


def test_global_config_clamps_saved_buffer_size() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        path.write_text('buffer_size = 46624\n')

        assert GlobalConfig.read(path).buffer_size == 4096
        assert tomllib.loads(path.read_text())['buffer_size'] == 4096


def test_global_config_stops_increasing_buffer_size_at_limit() -> None:
    with temporary_path() as tmp_path:
        config = GlobalConfig(buffer_size=4090, file=tmp_path / 'global.toml')

        assert config.increase_buffer_size() == 4096
        assert config.increase_buffer_size() == 4096


def test_frozen_errors_append_to_app_state_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        report_error('problem')

        log = tmp_path / 'tuney' / 'tuney.txt'
        assert 'problem' in log.read_text()


def test_instrument_appends_to_app_state_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        monkeypatch.setenv('TUNEY_TRACE', '1')

        instrument('clicked button', button='Play')

        log = tmp_path / 'tuney' / 'tuney.txt'
        assert "TRACE clicked button: button='Play'" in log.read_text()


def test_trace_requires_trace_environment(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        trace('note event', note=12)

        assert not (tmp_path / 'tuney' / 'tuney.txt').exists()


def test_trace_appends_to_app_state_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        monkeypatch.setenv('TUNEY_TRACE', '1')

        trace('note event', note=12)

        log = tmp_path / 'tuney' / 'tuney.txt'
        assert 'TRACE note event: note=12' in log.read_text()


def test_frozen_text_exit_appends_to_app_state_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        with pytest.raises(SystemExit) as error:
            exit_with_message('fatal')

        assert error.value.code == 1
        log = tmp_path / 'tuney' / 'tuney.txt'
        assert 'fatal' in log.read_text()


def test_frozen_thread_errors_append_to_app_state_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        def fail() -> None:
            raise RuntimeError('thread failed')

        start_thread(fail).join()

        log = tmp_path / 'tuney' / 'tuney.txt'
        assert 'RuntimeError: thread failed' in log.read_text()


def test_autosave_writes_current_model_without_app_state(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        app = App(
            gui=True,
            max_gap=2.0,
            text=[
                CharPress('a', time=0),
                CharPress('a', False, 100),
            ],
        )

        app._autosave.save(lambda path: save(app, path))

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


def test_restore_autosave_restores_gui_state_without_explicit_startup_data(
    monkeypatch,
) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(
            gui=True,
            max_gap=2.0,
            text=[
                CharPress('a', time=0),
                CharPress('a', False, 100),
            ],
        )
        saved._autosave.save(lambda path: save(saved, path))
        app = App(gui=True)

        app._autosave.restore(app)

        assert app.max_gap == 2.0
        assert app.char_presses == [
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ]


def test_restore_autosave_skips_when_startup_modifier_is_held(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(gui=True, max_gap=2.0)
        saved._autosave.save(lambda path: save(saved, path))
        app = App(gui=True)
        monkeypatch.setattr(
            'tuney.presets.autosave.startup_modifier_held', lambda: True
        )

        app._autosave.restore(app)

        assert app.max_gap == App().max_gap


def test_restore_autosave_skips_when_saved_state_disables_autosave(
    monkeypatch,
) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(gui=True, max_gap=2.0, load_autosave=False)
        saved._autosave.save(lambda path: save(saved, path))
        app = App(gui=True, max_gap=3.0)

        app._autosave.restore(app)

        assert app.max_gap == App().max_gap
        assert not app.load_autosave


def test_restore_autosave_ignores_invalid_state_file(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text('max_gap =')
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.max_gap == App().max_gap
    assert error is not None
    assert f'Could not restore {path}' in str(error)


def test_restore_autosave_defaults_invalid_fields(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text('max_gap = "bad"\nhover_time = 2.0\n')
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.max_gap == App().max_gap
        assert app.hover_time == 2.0
    assert error is not None
    assert f'Could not restore fields from {path}' in str(error)
    assert 'max_gap' in str(error)


def test_restore_autosave_defaults_invalid_nested_scale(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text(
            '\n'.join(
                [
                    'hover_time = 2.0',
                    '[scale]',
                    'note_names = "AB"',
                    'root = "C"',
                    'begin = "A"',
                    'end = "B"',
                ]
            )
        )
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.hover_time == 2.0
        assert app.scale == App().scale
    assert error is not None
    assert f'Could not restore fields from {path}' in str(error)
    assert 'root must be present in note_names' in str(error)


def test_restore_autosave_defaults_empty_ratios(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text(
            '\n'.join(
                [
                    '[tuning]',
                    'type = "ratios"',
                    '[tuning.ratios]',
                    'text = ""',
                ]
            )
        )
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.tuning.ratios is None
        assert app.tuning(69) == 440
    assert error is not None
    assert f'Could not restore fields from {path}' in str(error)
    assert 'No tuning ratios configured' in str(error)


def test_restore_autosave_does_not_override_explicit_text(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(gui=True, text=[CharPress('a', time=0)])
        saved._autosave.save(lambda path: save(saved, path))
        app = App(gui=True, text='b')

        app._autosave.restore(app)

        assert app.display_text == 'b'


def test_finished_replay_restarts_when_looping(monkeypatch) -> None:
    calls: list[str] = []
    app = App(gui=True, text=[CharPress('a', time=0)])
    main_window = FakeApp()
    main_window.is_replaying = True
    main_window.loop_replay = True
    app.__dict__['main_window'] = main_window
    monkeypatch.setattr('tuney.app.app.on_replay', lambda _: calls.append('replay'))

    app.key_recorder.finish_replay(app)

    assert calls == ['replay']
    assert main_window.is_replaying


def test_finished_empty_replay_stops_when_looping() -> None:
    app = App(gui=True)
    main_window = FakeApp()
    main_window.is_replaying = True
    main_window.loop_replay = True
    app.__dict__['main_window'] = main_window

    app.key_recorder.finish_replay(app)

    assert not main_window.is_replaying


def test_replay_moves_cursor_as_text_is_played(monkeypatch) -> None:
    class FakePlayer:
        @staticmethod
        def stop_all() -> None:
            pass

    class FakeSequencer:
        def __init__(
            self,
            char_presses: list[CharPress],
            callback: Callable[[CharPress | None], object],
        ) -> None:
            self.char_presses = char_presses
            self.callback = callback

        def start(self) -> None:
            for c in self.char_presses:
                self.callback(c)

        @staticmethod
        def stop() -> None:
            pass

    class FakeUi:
        def __init__(self) -> None:
            self.text: list[str] = []
            self.cursor: list[int | None] = []

        def set_text(self, text: str) -> None:
            self.text.append(text)

        def set_play_cursor(self, index: int | None) -> None:
            self.cursor.append(index)

    class FakeReplayWindow(FakeApp):
        def after(self, delay: int, callback: object, *args: object) -> str:
            assert delay == 0
            assert callable(callback)
            callback(*args)
            return 'after-0'

    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
            CharPress('b', time=200),
        ],
    )
    main_window = FakeReplayWindow()
    main_window.is_replaying = True
    main_window.ui = FakeUi()
    app.__dict__['main_window'] = main_window
    app.__dict__['player'] = FakePlayer()
    monkeypatch.setattr('tuney.recorders.key_recorder.Sequencer', FakeSequencer)
    monkeypatch.setattr('tuney.app.app.play_char', lambda *_: None)

    app.key_recorder.on_replay(app)

    assert main_window.ui.text == ['', 'a', 'ab']
    assert main_window.ui.cursor == [0, 1, 2]


def test_replay_starts_speech(monkeypatch) -> None:
    class FakePlayer:
        def __init__(self) -> None:
            self.speech: list[tuple[str, float, float]] = []

        @staticmethod
        def stop_all() -> None:
            pass

        def start_speech(self, text: str, duration: float, level: float) -> None:
            self.speech.append((text, duration, level))

    class FakeSequencer:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        @staticmethod
        def start() -> None:
            pass

    app = App(
        gui=True,
        use_speech=True,
        speech_level=0.5,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
            CharPress('b', time=200),
            CharPress('b', False, 400),
        ],
    )
    main_window = FakeApp()
    main_window.is_replaying = True
    app.__dict__['main_window'] = main_window
    player = FakePlayer()
    app.__dict__['player'] = player
    monkeypatch.setattr('tuney.recorders.key_recorder.Sequencer', FakeSequencer)

    app.key_recorder.on_replay(app)

    assert player.speech == [('ab', 0.4, 0.5)]


def test_replay_char_presses_use_loop_tempo() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 1000),
        ],
    )
    main_window = FakeApp()
    main_window.loop_tempo = 2.0
    app.__dict__['main_window'] = main_window

    assert replay_char_presses(app) == [
        CharPress('a', time=0),
        CharPress('a', False, 500),
    ]


def test_replay_char_presses_cut_loop_start_and_end() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
            CharPress('b', time=1000),
            CharPress('b', False, 1500),
        ],
    )
    main_window = FakeApp()
    main_window.loop_before = 0.5
    main_window.loop_after = 0.25
    app.__dict__['main_window'] = main_window

    assert replay_char_presses(app) == [
        CharPress('a', False, 0),
        CharPress('b', time=500),
    ]


def test_replay_char_presses_add_loop_start_and_end_space() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
        ],
    )
    main_window = FakeApp()
    main_window.loop_before = -0.25
    main_window.loop_after = -0.75
    app.__dict__['main_window'] = main_window

    assert replay_char_presses(app) == [
        CharPress('a', time=250),
        CharPress('a', False, 750),
        CharPress(time=1500),
    ]


def test_loop_randomize_replaces_playback_timing_without_changing_recording() -> None:
    app = App(
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
    main_window = FakeApp()
    main_window.loop_replay = True
    main_window.randomize_on_each_loop = True
    app.__dict__['main_window'] = main_window
    recorded_char_presses = list(app.char_presses)

    first_loop = replay_char_presses(app)
    second_loop = replay_char_presses(app)

    assert app.char_presses == recorded_char_presses
    assert first_loop != recorded_char_presses
    assert second_loop != first_loop
    assert ''.join(c.char for c in first_loop if c.is_press) == 'abcd'
    assert ''.join(c.char for c in second_loop if c.is_press) == 'abcd'


def test_randomize_on_each_loop_only_affects_loop_replay() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
        text_timings=TextTimings(seed=1, overlap=0, timings=[10, 20, 30]),
    )
    main_window = FakeApp()
    main_window.randomize_on_each_loop = True
    app.__dict__['main_window'] = main_window

    assert replay_char_presses(app) == app.char_presses


def test_on_char_ignores_input_while_saving():
    app = App(gui=True)
    main_window = FakeApp()
    main_window.is_saving = True
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('a', time=100.0))

    assert app.char_presses == []


def test_on_char_ignores_input_without_app_focus():
    app = App(gui=True)
    main_window = FakeApp()
    main_window.has_focus = False
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('a', time=100.0))

    assert app.char_presses == []


def test_on_char_ignores_input_with_control_panel_focus():
    app = App(gui=True)
    main_window = FakeApp()
    main_window.focus_in_control_panel = True
    app.__dict__['main_window'] = main_window

    on_char(app, CharPress('a', time=100.0))

    assert app.char_presses == []


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
    app = App(
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )

    run(app)

    assert events == [(20, True), (20, False)]
    assert lifecycle == ['stop_all', 'wait', 'close']
    assert 'main_window' not in app.__dict__
    assert 'listener' not in app.__dict__


def test_cli_mode_prints_characters_as_they_play(
    monkeypatch,
) -> None:
    printed: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(Player, 'on_note', lambda *args: True)
    monkeypatch.setattr(
        'builtins.print',
        lambda *args, **kwargs: printed.append((args, kwargs)),
    )
    app = App(
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
            CharPress('b', time=0),
            CharPress('b', False, 0),
        ],
    )

    play_cli(app)

    assert printed == [
        (('a',), {'end': '', 'flush': True}),
        (('b',), {'end': '', 'flush': True}),
        ((), {}),
    ]


def test_cli_mode_prints_newline_before_keyboard_interrupt(
    monkeypatch,
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
    app = App(text=[CharPress('a', time=0)])
    try:
        play_cli(app)
    except KeyboardInterrupt:
        interrupted = True

    assert interrupted
    assert printed == [
        (('a',), {'end': '', 'flush': True}),
        ((), {}),
    ]


def test_cli_mode_requires_text(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run(App())

    error = capsys.readouterr().err
    assert exc_info.value.code == 2
    assert 'Required options were not provided: TEXT' in error
    assert 'For full helptext, run tuney --help' in error


def test_cli_mode_requires_sound() -> None:
    with pytest.raises(SystemExit, match='CLI mode requires sound'):
        run(App(silent=True, text='a'))


def test_output_forces_cli_mode() -> None:
    app = App(gui=True, output=Path('out.wav'))

    assert not app.gui


def test_silent_cli_mode_writes_audio_file(monkeypatch) -> None:
    path = Path('out.wav')
    rendered: list[
        tuple[Path, list[tuple[int, NotePress]], Callable[[], str] | None]
    ] = []

    def render_file(
        self: Player,
        output: Path,
        events: list[tuple[int, NotePress]],
        comment: Callable[[], str] | None,
    ) -> None:
        rendered.append((output, events, comment))

    monkeypatch.setattr(Player, 'render_file', render_file)
    app = App(
        output=path,
        silent=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
    )

    run(app)
    output, events, comment = rendered[0]

    assert output == path
    assert app.player.tuning == app.tuning
    assert [(frame, note.is_press) for frame, note in events] == [
        (0, True),
        (4800, False),
    ]
    assert callable(comment)


def test_text_file_output_writes_midi_file_without_audio(monkeypatch, tmp_path) -> None:
    def audio_call(*_: object) -> None:
        raise AssertionError('MIDI file output should not use audio')

    monkeypatch.setattr(Player, 'render_file', audio_call)
    monkeypatch.setattr(Player, 'stop_all', audio_call)
    text = tmp_path / 'input.txt'
    text.write_text('a')
    path = tmp_path / 'out.smf'
    app = App(
        output=path,
        text_file=text,
        text_timings=TextTimings(seed=1, overlap=0, timings=[100]),
    )

    run(app)

    file = mido.MidiFile(path)
    messages = [
        message for track in file.tracks for message in track if not message.is_meta
    ]

    assert file.ticks_per_beat == 1000
    assert messages[0].type == 'program_change'
    assert messages[0].time == 0
    assert messages[0].program == app.midi.output.program
    assert [(i.type, i.time, i.note, i.velocity) for i in messages[1:]] == [
        ('note_on', 0, app.midi.output.midi_note(app.mapper('a')), 64),
        ('note_on', 100, app.midi.output.midi_note(app.mapper('a')), 0),
    ]


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
        'tuney.app.app.play_cli',
        lambda _: lifecycle.append('play_cli'),
    )
    app = App(
        output=path,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )
    run(app)

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

        def interrupt(
            self: Player,
            output: Path,
            events: list[tuple[int, NotePress]],
            comment: Callable[[], str] | None,
        ) -> None:
            output.write_bytes(b'partial')
            raise KeyboardInterrupt

        monkeypatch.setattr(Player, 'render_file', interrupt)
        app = App(output=path, silent=True, text='a')

        with pytest.raises(KeyboardInterrupt):
            run(app)

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
        app = App(gui=True)
        assert on_transport_state(app, State.ready, State.recording, Action.record)
        comment = app.audio_recorder.comment
        assert on_transport_state(app, State.recording, State.paused, Action.record)
        assert on_transport_state(app, State.paused, State.recording, Action.record)
        assert on_transport_state(
            app, State.recording, State.ready, Action.save, output
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
        assert app.audio_recorder.path is None
        assert app.audio_recorder.comment is None


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
    app = App(gui=True)

    assert on_transport_state(app, State.ready, State.recording, Action.record)
    recording_path = app.audio_recorder.path

    assert not on_transport_state(app, State.recording, State.ready, Action.save)
    assert app.audio_recorder.path == recording_path
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
    app = App(gui=True)

    assert on_transport_state(app, State.ready, State.recording, Action.record)
    recording_path = app.audio_recorder.path
    assert recording_path is not None

    assert on_transport_state(app, State.recording, State.ready, Action.clear)

    assert lifecycle[0][0] == 'start_recording'
    assert lifecycle[1] == 'stop_recording'
    assert not recording_path.exists()
    assert app.audio_recorder.path is None
    assert app.audio_recorder.comment is None
