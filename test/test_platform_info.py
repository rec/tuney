import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from queue import SimpleQueue
from urllib.parse import parse_qs, urlparse

from tuney.app import platform_info
from tuney.app.app import App
from tuney.midi.listener import MidiListener
from tuney.midi.midi import Midi
from tuney.time.char_press import CharPress
from tuney.ui import error_dialogs
from tuney.ui.main_window import MainWindow

from .app_helpers import temporary_path


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
        url = platform_info.error_issue_url(error, path)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert f'{parsed.scheme}://{parsed.netloc}{parsed.path}' == platform_info.ISSUE_URL
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

        url = platform_info.crash_issue_url(log)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f'{parsed.scheme}://{parsed.netloc}{parsed.path}' == platform_info.ISSUE_URL
    assert query['title'] == ['Tuney crashed']
    body = query['body'][0]
    assert 'Tuney appears to have crashed during the previous run.' in body
    assert 'TRACE one\nTRACE two' in body


def test_crash_issue_url_describes_empty_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        log = tmp_path / 'tuney' / 'tuney.txt'
        log.parent.mkdir(parents=True)
        log.write_text('\n')

        url = platform_info.crash_issue_url(log)

    body = parse_qs(urlparse(url).query)['body'][0]
    assert 'No text found in crash report' in body


def test_crash_report_brings_window_forward(monkeypatch) -> None:
    calls = []

    class Window:
        def show(self) -> None:
            calls.append('window show')

        def raise_(self) -> None:
            calls.append('window raise')

        def activateWindow(self) -> None:
            calls.append('window activate')

    class MessageBox:
        class Icon:
            Question = object()

        class StandardButton:
            Yes = 1
            No = 2

        def __init__(self, parent: object) -> None:
            calls.append(('dialog', parent))

        def setIcon(self, icon: object) -> None:
            calls.append(('icon', icon))

        def setWindowTitle(self, title: str) -> None:
            calls.append(('title', title))

        def setText(self, text: str) -> None:
            calls.append(('text', text))

        def setStandardButtons(self, buttons: object) -> None:
            calls.append(('buttons', buttons))

        def setDefaultButton(self, button: object) -> None:
            calls.append(('default', button))

        def setWindowFlag(self, flag: object, enabled: bool) -> None:
            calls.append(('flag', flag, enabled))

        def show(self) -> None:
            calls.append('dialog show')

        def raise_(self) -> None:
            calls.append('dialog raise')

        def activateWindow(self) -> None:
            calls.append('dialog activate')

        def exec(self) -> object:
            calls.append('exec')
            return MessageBox.StandardButton.No

    monkeypatch.setattr(error_dialogs.QtWidgets, 'QMessageBox', MessageBox)

    window = Window()

    error_dialogs.show_crash_report(window)

    assert calls == [
        'window show',
        'window raise',
        'window activate',
        ('dialog', window),
        ('icon', MessageBox.Icon.Question),
        ('title', 'File issue?'),
        (
            'text',
            'Tuney appears to have crashed during the previous run.\n\nFile issue?',
        ),
        ('buttons', MessageBox.StandardButton.Yes | MessageBox.StandardButton.No),
        ('default', MessageBox.StandardButton.Yes),
        ('flag', error_dialogs.Qt.WindowType.WindowStaysOnTopHint, True),
        'dialog show',
        'dialog raise',
        'dialog activate',
        'exec',
    ]


def test_report_problem_dialog_asks_before_opening_issue(monkeypatch) -> None:
    calls = []

    class Signal:
        def __init__(self, name: str) -> None:
            self.name = name

        def connect(self, callback: Callable[[], None]) -> None:
            calls.append(('connect', self.name, callback.__name__))

    class Dialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, parent: object) -> None:
            calls.append(('dialog', parent))

        def setWindowTitle(self, title: str) -> None:
            calls.append(('title', title))

        def accept(self) -> None:
            calls.append('accept')

        def reject(self) -> None:
            calls.append('reject')

        def exec(self) -> int:
            calls.append('exec')
            return Dialog.DialogCode.Accepted

    class PushButton:
        def __init__(self, text: str, parent: object) -> None:
            self.checked = False
            calls.append(('push', text, parent))

        def setCheckable(self, checkable: bool) -> None:
            calls.append(('checkable', checkable))

        def setChecked(self, checked: bool) -> None:
            self.checked = checked
            calls.append(('checked', checked))

        def isChecked(self) -> bool:
            return self.checked

    class Label:
        def __init__(self, text: str, parent: object) -> None:
            calls.append(('label', text, parent))

    class BoxLayout:
        def __init__(self, parent: object | None = None) -> None:
            calls.append(('layout', parent))

        def addWidget(self, widget: object) -> None:
            calls.append(('widget', type(widget).__name__))

        def addLayout(self, layout: object) -> None:
            calls.append(('sub_layout', type(layout).__name__))

    class ButtonBox:
        class StandardButton:
            Yes = 1
            Cancel = 2

        def __init__(self, buttons: object, parent: object) -> None:
            self.accepted = Signal('accepted')
            self.rejected = Signal('rejected')
            calls.append(('buttons', buttons, parent))

    monkeypatch.setattr(error_dialogs.QtWidgets, 'QDialog', Dialog)
    monkeypatch.setattr(error_dialogs.QtWidgets, 'QPushButton', PushButton)
    monkeypatch.setattr(error_dialogs.QtWidgets, 'QLabel', Label)
    monkeypatch.setattr(error_dialogs.QtWidgets, 'QHBoxLayout', BoxLayout)
    monkeypatch.setattr(error_dialogs.QtWidgets, 'QVBoxLayout', BoxLayout)
    monkeypatch.setattr(error_dialogs.QtWidgets, 'QDialogButtonBox', ButtonBox)

    window = object()

    assert error_dialogs.report_problem_options(window) == (
        error_dialogs.ProblemReportOptions(
            include_log=False,
            include_snapshot=False,
        )
    )
    assert ('title', 'Report a problem') in calls
    assert any(i[:2] == ('push', 'Include log?') for i in calls)
    assert any(i[:2] == ('push', 'Include snapshot?') for i in calls)
    assert ('checked', False) in calls
    assert any(i[:2] == ('label', 'Open an issue on Github?') for i in calls)
    assert any(
        i[:2]
        == (
            'label',
            'Turn this on if the problem just happened a few seconds ago',
        )
        for i in calls
    )
    assert any(i[:2] == ('label', 'Save a picture of the Tuney window') for i in calls)
    assert any(
        i[:2]
        == ('buttons', ButtonBox.StandardButton.Yes | ButtonBox.StandardButton.Cancel)
        for i in calls
    )
    assert ('connect', 'accepted', 'accept') in calls
    assert ('connect', 'rejected', 'reject') in calls


def test_problem_issue_url_includes_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        log = tmp_path / 'tuney' / 'tuney.txt'
        log.parent.mkdir(parents=True)
        log.write_text('TRACE problem\n')

        url = platform_info.problem_issue_url(log)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f'{parsed.scheme}://{parsed.netloc}{parsed.path}' == platform_info.ISSUE_URL
    assert query['title'] == ['Tuney problem report']
    body = query['body'][0]
    assert 'Problem report from Tuney.' in body
    assert 'TRACE problem' in body


def test_problem_issue_url_includes_snapshot_path(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        log = tmp_path / 'tuney' / 'tuney.txt'
        snapshot = tmp_path / 'tuney' / 'snapshots' / 'tuney.png'
        log.parent.mkdir(parents=True)
        log.write_text('TRACE problem\n')

        url = platform_info.problem_issue_url(log, snapshot_path=snapshot)

    body = parse_qs(urlparse(url).query)['body'][0]
    assert '## Snapshot' in body
    assert f'Saved locally: {snapshot}' in body


def test_problem_issue_url_can_omit_log(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        log = tmp_path / 'tuney' / 'tuney.txt'
        log.parent.mkdir(parents=True)
        log.write_text('TRACE problem\n')

        url = platform_info.problem_issue_url(log, include_log=False)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f'{parsed.scheme}://{parsed.netloc}{parsed.path}' == platform_info.ISSUE_URL
    assert query['title'] == ['Tuney problem report']
    body = query['body'][0]
    assert 'Problem report from Tuney.' in body
    assert 'TRACE problem' not in body
    assert f'Log file: {log}' not in body
    assert '## Log' not in body


def test_save_problem_snapshot_grabs_tuney_ui(monkeypatch) -> None:
    saved_paths = []

    class Pixmap:
        @staticmethod
        def save(path: str, format_name: str) -> bool:
            saved_paths.append((Path(path), format_name))
            return True

    class Ui:
        @staticmethod
        def grab() -> Pixmap:
            return Pixmap()

    class Window:
        ui = Ui()

    with temporary_path() as tmp_path:
        monkeypatch.setattr(
            error_dialogs.platform_info,
            'app_state_dir',
            lambda: tmp_path / 'tuney',
        )

        path = error_dialogs.save_problem_snapshot(Window())

    assert path.parent == tmp_path / 'tuney' / 'snapshots'
    assert path.name.startswith('tuney-')
    assert path.suffix == '.png'
    assert saved_paths == [(path, 'PNG')]


def test_app_user_model_id_is_windows_only(monkeypatch) -> None:
    calls = []

    class Shell32:
        @staticmethod
        def SetCurrentProcessExplicitAppUserModelID(app_id: str) -> int:
            calls.append(app_id)
            return 0

    class Windll:
        shell32 = Shell32()

    monkeypatch.setattr(platform_info.sys, 'platform', 'darwin')
    monkeypatch.setattr(platform_info.ctypes, 'windll', Windll(), raising=False)

    platform_info.set_windows_app_user_model_id()

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

    monkeypatch.setattr(platform_info.sys, 'platform', 'win32')
    monkeypatch.setattr(platform_info.ctypes, 'windll', Windll(), raising=False)

    platform_info.set_windows_app_user_model_id()

    assert calls == [platform_info.APP_USER_MODEL_ID]


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

    monkeypatch.setattr(platform_info.ctypes, 'windll', Windll(), raising=False)

    assert platform_info._windows_process_is_alive(1234)
    assert calls == [
        ('open', 0x1000, False, 1234),
        ('exit', handle),
        ('close', handle),
    ]


def test_audio_diagnostics_use_reportable_dialog() -> None:
    class FakeDiagnostics:
        def take_errors(self) -> list[str]:
            return ['cannot render block']

    class FakeEngine:
        diagnostics = FakeDiagnostics()

        def process_notifications(self) -> None:
            pass

    class FakePlayer:
        def __init__(self) -> None:
            self.engine = FakeEngine()

    class FakeApp:
        player = FakePlayer()
        midi_listener = MidiListener(Midi(), lambda note, is_press: None)

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

        assert not platform_info.mark_session_started()
        assert not platform_info.mark_session_started()
        platform_info.crash_marker_path().write_text('123456')
        monkeypatch.setattr(platform_info, '_process_is_alive', lambda _: False)
        assert platform_info.mark_session_started()
        platform_info.mark_session_clean_exit()
        assert not platform_info.mark_session_started()


def test_crash_marker_clean_exit_only_removes_current_process(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        platform_info.crash_marker_path().parent.mkdir(parents=True)
        platform_info.crash_marker_path().write_text('123456')

        platform_info.mark_session_clean_exit()

        assert platform_info.crash_marker_path().exists()


def test_single_instance_lock_blocks_second_instance(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        platform_info.instance_lock_path().parent.mkdir(parents=True)
        platform_info.instance_lock_path().write_text(str(os.getpid()))

        assert not platform_info.acquire_single_instance()
        platform_info.instance_lock_path().unlink()
        assert platform_info.acquire_single_instance()
        platform_info.release_single_instance()


def test_single_instance_lock_replaces_stale_lock(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        platform_info.instance_lock_path().parent.mkdir(parents=True)
        platform_info.instance_lock_path().write_text('123456')
        monkeypatch.setattr(platform_info, '_process_is_alive', lambda _: False)

        assert platform_info.acquire_single_instance()
        platform_info.release_single_instance()


def test_gui_run_exits_when_another_instance_is_running(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        calls: list[str] = []
        platform_info.instance_lock_path().parent.mkdir(parents=True)
        platform_info.instance_lock_path().write_text(str(os.getpid()))

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
            platform_info,
            'show_already_running',
            lambda: calls.append('busy'),
        )

        App.run(FakeApp())

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
        app.start = lambda: None

        App.run(app)

        assert isinstance(window.error, RuntimeError)
        assert calls == ['restore', 'window', 'error', 'mainloop']


def test_run_reports_previous_gui_crash(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        platform_info.crash_marker_path().parent.mkdir(parents=True)
        platform_info.crash_marker_path().write_text('123456')
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

            @staticmethod
            def start() -> None:
                pass

        monkeypatch.setattr(platform_info, '_process_is_alive', lambda _: False)
        App.run(FakeApp())

        assert calls == ['restore', 'crash', 'mainloop']
        assert not platform_info.crash_marker_path().exists()
