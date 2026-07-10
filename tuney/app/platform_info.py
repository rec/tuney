from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from traceback import format_exception
from types import TracebackType
from typing import NoReturn

XDG_STATE_HOME = 'XDG_STATE_HOME'
APP_STATE_DIR = Path('tuney')
LOG_FILE = 'tuney.txt'


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


def append_log(message: str) -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open('a') as fp:
        print(f'[{timestamp}] {message}', file=fp)
    return path


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


def show_frozen_exception(error: BaseException, path: Path) -> None:
    message = (
        f'Tuney encountered an error and wrote details to:\n\n{path}\n\n'
        f'{type(error).__name__}: {error}'
    )
    if sys.platform == 'win32':
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, 'Tuney error', 0x10)
        return
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        _ = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, 'Tuney error', message)
        return
    except (ImportError, RuntimeError):
        pass
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
