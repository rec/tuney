from __future__ import annotations

import ctypes
import os
import platform
import sys
from ctypes import wintypes
from pathlib import Path
from traceback import format_exception
from typing import NoReturn
from urllib.parse import urlencode

from reccy import logging

XDG_STATE_HOME = 'XDG_STATE_HOME'
XDG_CONFIG_HOME = 'XDG_CONFIG_HOME'
APP_STATE_DIR = Path('tuney')
LOG_FILE = 'tuney.log'
CRASH_MARKER_FILE = 'running.txt'
INSTANCE_LOCK_FILE = 'instance.lock'
ISSUE_URL = 'https://github.com/rec/tuney/issues/new'
MAX_ISSUE_BODY = 6000
APP_USER_MODEL_ID = 'rec.tuney.Tuney'

_instance_lock_fd: int | None = None
_instance_lock_path: Path | None = None
LOGGER = logging.get_logger(__name__)


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


def set_windows_app_user_model_id() -> None:
    if sys.platform != 'win32':
        return
    try:
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except (AttributeError, OSError) as error:
        LOGGER.error('Could not set Windows app user model ID: %s', error)
        return
    if result:
        LOGGER.error('Could not set Windows app user model ID: %s', result)


def log_path() -> Path:
    return app_state_dir() / LOG_FILE


def crash_marker_path() -> Path:
    return app_state_dir() / CRASH_MARKER_FILE


def instance_lock_path() -> Path:
    return app_state_dir() / INSTANCE_LOCK_FILE


def configure_logging() -> None:
    if is_frozen():
        logging.configure(log_path())
        return
    logging.configure()


def instrument(event: str, **data: object) -> None:
    LOGGER.info('%s: %s', event, data)


def trace(event: str, **data: object) -> None:
    LOGGER.debug('%s: %s', event, data)


def report_error(message: str) -> None:
    LOGGER.error(message)


def exit_with_message(message: str, code: int | None = None) -> NoReturn:
    if is_frozen():
        LOGGER.error(message)
        sys.exit(1 if code is None else code)
    if code is not None:
        print(message, file=sys.stderr)
        sys.exit(code)
    sys.exit(message)


def log_exception(error: BaseException) -> Path:
    LOGGER.error('%s', error, exc_info=(type(error), error, error.__traceback__))
    return log_path()


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


def acquire_single_instance() -> bool:
    global _instance_lock_fd, _instance_lock_path

    if _instance_lock_fd is not None:
        return True
    path = instance_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if _marker_process_is_alive(path):
                return False
            try:
                path.unlink()
            except OSError:
                return False
            continue
        except OSError:
            return False
        try:
            os.write(fd, str(os.getpid()).encode())
        except OSError:
            os.close(fd)
            path.unlink(missing_ok=True)
            return False
        _instance_lock_fd = fd
        _instance_lock_path = path
        return True
    return False


def release_single_instance() -> None:
    global _instance_lock_fd, _instance_lock_path

    fd, path = _instance_lock_fd, _instance_lock_path
    _instance_lock_fd = None
    _instance_lock_path = None
    if fd is not None:
        os.close(fd)
    if path is not None and _marker_pid(path) == os.getpid():
        path.unlink(missing_ok=True)


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
    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.__dict__['windll'].kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    exit_code = wintypes.DWORD()
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


def problem_issue_url(
    path: Path, *, include_log: bool = True, snapshot_path: Path | None = None
) -> str:
    if include_log:
        return log_issue_url(
            path,
            'Tuney problem report',
            'Problem report from Tuney.',
            snapshot_path=snapshot_path,
        )
    lines = [
        '## Error',
        '',
        'Problem report from Tuney.',
        '',
        '## Environment',
        '',
        f'- Platform: {platform.platform()}',
        f'- Python: {platform.python_version()}',
        f'- Frozen app: {is_frozen()}',
    ]
    if snapshot_path is not None:
        lines.extend(['', '## Snapshot', '', f'Saved locally: {snapshot_path}'])
    report = '\n'.join(lines)
    return f'{ISSUE_URL}?{urlencode({"title": "Tuney problem report", "body": report})}'


def log_issue_url(
    path: Path, title: str, message: str, *, snapshot_path: Path | None = None
) -> str:
    try:
        log = path.read_text(errors='replace')
    except OSError as error:
        log = f'Could not read {path}: {error}'
    if not log.strip():
        log = 'No text found in crash report'
    lines = [
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
    if snapshot_path is not None:
        lines.extend(['', '## Snapshot', '', f'Saved locally: {snapshot_path}'])
    report = '\n'.join(lines)
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


def show_already_running() -> None:
    message = 'Tuney is already running.'
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        _ = QApplication.instance() or QApplication([])
        QMessageBox.information(None, 'Tuney', message)
        return
    except (ImportError, RuntimeError):
        pass
    if sys.platform == 'win32':
        import ctypes

        windll = ctypes.__dict__['windll']
        windll.user32.MessageBoxW(None, message, 'Tuney', 0x40)
        return
    print(message, file=sys.stderr)


def handle_frozen_exception(error: BaseException) -> NoReturn:
    path = log_exception(error)
    show_frozen_exception(error, path)
    sys.exit(1)
