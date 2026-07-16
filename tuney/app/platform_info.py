from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from traceback import format_exception
from types import TracebackType
from typing import NoReturn
from urllib.parse import urlencode

XDG_STATE_HOME = 'XDG_STATE_HOME'
XDG_CONFIG_HOME = 'XDG_CONFIG_HOME'
TUNEY_TRACE = 'TUNEY_TRACE'
APP_STATE_DIR = Path('tuney')
LOG_FILE = 'tuney.txt'
CRASH_MARKER_FILE = 'running.txt'
ISSUE_URL = 'https://github.com/rec/tuney/issues/new'
MAX_ISSUE_BODY = 6000


def app_config_dir() -> Path:
    if (config_home := os.environ.get(XDG_CONFIG_HOME)) and Path(
        config_home
    ).is_absolute():
        return Path(config_home) / APP_STATE_DIR
    return Path.home() / '.config' / APP_STATE_DIR


def app_state_dir() -> Path:
    if (state_home := os.environ.get(XDG_STATE_HOME)) and Path(
        state_home
    ).is_absolute():
        return Path(state_home) / APP_STATE_DIR
    return Path.home() / '.local' / 'state' / APP_STATE_DIR


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def log_path() -> Path:
    return app_state_dir() / LOG_FILE


def crash_marker_path() -> Path:
    return app_state_dir() / CRASH_MARKER_FILE


def append_log(message: str) -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open('a') as fp:
        print(f'[{timestamp}] {message}', file=fp)
    return path


def instrument(event: str, **data: object) -> None:
    if not is_frozen() and os.environ.get(TUNEY_TRACE) != '1':
        return
    _append_trace(event, data)


def trace(event: str, **data: object) -> None:
    if os.environ.get(TUNEY_TRACE) != '1':
        return
    _append_trace(event, data)


def _append_trace(event: str, data: dict[str, object]) -> None:
    details = ' '.join(f'{k}={v!r}' for k, v in data.items())
    try:
        append_log(f'TRACE {event}{": " + details if details else ""}')
    except OSError:
        pass


def report_error(message: str) -> None:
    if is_frozen():
        append_log(message)
    else:
        print(message, file=sys.stderr)


def exit_with_message(message: str, code: int | None = None) -> NoReturn:
    if is_frozen():
        append_log(message)
        sys.exit(1 if code is None else code)
    if code is not None:
        print(message, file=sys.stderr)
        sys.exit(code)
    sys.exit(message)


def log_exception(error: BaseException) -> Path:
    return append_log(''.join(format_exception(error)).rstrip())


def mark_session_started() -> bool:
    path = crash_marker_path()
    crashed = False
    if path.exists():
        crashed = not _marker_process_is_alive(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if crashed or not path.exists():
            path.write_text(str(os.getpid()))
    except OSError:
        return False
    return crashed


def mark_session_clean_exit() -> None:
    try:
        path = crash_marker_path()
        if _marker_pid(path) == os.getpid():
            path.unlink(missing_ok=True)
    except OSError:
        pass


def _marker_process_is_alive(path: Path) -> bool:
    if (pid := _marker_pid(path)) is None:
        return False
    return _process_is_alive(pid)


def _marker_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == 'win32':
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _windows_process_is_alive(pid: int) -> bool:
    import ctypes

    process_query_limited_information = 0x1000
    still_active = 259
    windll = ctypes.__dict__['windll']
    kernel32 = windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    exit_code = ctypes.c_ulong()
    try:
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def error_issue_url(error: BaseException, path: Path) -> str:
    lines = str(error).splitlines()
    title = f'{type(error).__name__}: {lines[0] if lines else "(no message)"}'
    report = '\n'.join(
        [
            '## Error',
            '',
            f'{type(error).__name__}: {error}',
            '',
            '## Environment',
            '',
            f'- Platform: {platform.platform()}',
            f'- Python: {platform.python_version()}',
            f'- Frozen app: {is_frozen()}',
            f'- Log file: {path}',
            '',
            '## Traceback',
            '',
            '```text',
            ''.join(format_exception(error)).rstrip(),
            '```',
        ]
    )
    if len(report) > MAX_ISSUE_BODY:
        report = f'{report[:MAX_ISSUE_BODY]}\n\n[truncated]'
    return f'{ISSUE_URL}?{urlencode({"title": title[:120], "body": report})}'


def crash_issue_url(path: Path) -> str:
    return log_issue_url(
        path,
        'Tuney crashed',
        'Tuney appears to have crashed during the previous run.',
    )


def problem_issue_url(path: Path) -> str:
    return log_issue_url(path, 'Tuney problem report', 'Problem report from Tuney.')


def log_issue_url(path: Path, title: str, message: str) -> str:
    try:
        log = path.read_text(errors='replace')
    except OSError as error:
        log = f'Could not read {path}: {error}'
    report = '\n'.join(
        [
            '## Error',
            '',
            message,
            '',
            '## Environment',
            '',
            f'- Platform: {platform.platform()}',
            f'- Python: {platform.python_version()}',
            f'- Frozen app: {is_frozen()}',
            f'- Log file: {path}',
            '',
            '## Log',
            '',
            '```text',
            log[-MAX_ISSUE_BODY:],
            '```',
        ]
    )
    return f'{ISSUE_URL}?{urlencode({"title": title, "body": report})}'


def show_frozen_exception(error: BaseException, path: Path) -> None:
    message = (
        f'Tuney encountered an error and wrote details to:\n\n{path}\n\n'
        f'{type(error).__name__}: {error}'
    )
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QApplication, QMessageBox

        _ = QApplication.instance() or QApplication([])
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle('Tuney error')
        dialog.setText(message)
        report = dialog.addButton('Report Issue', QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Ok)
        dialog.exec()
        if dialog.clickedButton() is report:
            QDesktopServices.openUrl(QUrl(error_issue_url(error, path)))
        return
    except (ImportError, RuntimeError):
        pass
    if sys.platform == 'win32':
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, 'Tuney error', 0x10)
        return
    print(message, file=sys.stderr)


def handle_frozen_exception(error: BaseException) -> NoReturn:
    path = log_exception(error)
    show_frozen_exception(error, path)
    sys.exit(1)


def frozen_excepthook(
    cls: type[BaseException],
    error: BaseException,
    traceback: TracebackType | None,
) -> None:
    path = append_log(''.join(format_exception(cls, error, traceback)).rstrip())
    show_frozen_exception(error, path)


def install_frozen_excepthook() -> None:
    if is_frozen():
        sys.excepthook = frozen_excepthook
