from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

XDG_STATE_HOME = 'XDG_STATE_HOME'
APP_STATE_DIR = Path('tuney')
LOG_FILE = 'tuney.log'


def app_state_dir() -> Path:
    state_home = os.environ.get(XDG_STATE_HOME)
    if state_home and Path(state_home).is_absolute():
        return Path(state_home) / APP_STATE_DIR
    return Path.home() / '.local' / 'state' / APP_STATE_DIR


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def append_log(message: str) -> None:
    path = app_state_dir() / LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open('a') as fp:
        print(f'[{timestamp}] {message}', file=fp)


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
