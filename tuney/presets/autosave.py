from __future__ import annotations

import os
import sys
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from . import read_file

if TYPE_CHECKING:
    from ..tuney import Tuney

XDG_STATE_HOME = 'XDG_STATE_HOME'
AUTOSAVE_FILE = Path('tuney') / 'state.toml'


class Autosave(BaseModel, frozen=True):
    file: Path | None = None

    @cached_property
    def path(self) -> Path:
        if self.file is not None:
            return self.file
        state_home = os.environ.get(XDG_STATE_HOME)
        if state_home and Path(state_home).is_absolute():
            return Path(state_home) / AUTOSAVE_FILE
        return Path.home() / '.local' / 'state' / AUTOSAVE_FILE

    def save(self, save: Callable[[Path], None]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        save(self.path)

    def restore(self, t: Tuney) -> None:
        if not (
            t.gui
            and self.path.exists()
            and not (t.config_file or t.preset or t.text or t.text_args)
        ):
            return
        try:
            data = read_file(self.path)
        except (OSError, ValueError) as error:
            print(f'Could not restore {self.path}: {error}', file=sys.stderr)
            return
        while True:
            try:
                t.restore_data(data)
                return
            except ValidationError as error:
                print(
                    f'Could not restore fields from {self.path}: {error}',
                    file=sys.stderr,
                )
                if not any(_delete_data_path(data, e['loc']) for e in error.errors()):
                    return


def _delete_data_path(data: dict[str, object], loc: tuple[object, ...]) -> bool:
    # Remove a value that failed validation from loaded autosave data.
    # Return True if a value was deleted, otherwise False.
    current: object = data
    for part in loc[:-1]:
        if isinstance(part, str) and isinstance(current, dict):
            current = current.get(part)
        elif isinstance(part, int) and isinstance(current, list):
            if part < 0 or part >= len(current):
                return False
            current = current[part]
        else:
            return False
    if not loc:
        return False
    last = loc[-1]
    if isinstance(last, str) and isinstance(current, dict) and last in current:
        del current[last]
        return True
    if isinstance(last, int) and isinstance(current, list):
        if last < 0 or last >= len(current):
            return False
        del current[last]
        return True
    return False
