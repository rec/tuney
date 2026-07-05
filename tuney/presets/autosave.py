from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from ..platform_info import app_state_dir, report_error
from . import read_file

if TYPE_CHECKING:
    from ..tuney_state import TuneyState

AUTOSAVE_FILE = Path('tuney') / 'state.toml'


class Autosave(BaseModel, frozen=True):
    file: Path | None = None

    @cached_property
    def path(self) -> Path:
        if self.file is not None:
            return self.file
        return app_state_dir() / AUTOSAVE_FILE.name

    def save(self, save: Callable[[Path], None]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        save(self.path)

    def restore(self, state: TuneyState) -> None:
        tuney = state.tuney
        if not (
            tuney.gui
            and not tuney.skip_startup_files
            and self.path.exists()
            and not (tuney.config_file or tuney.preset or tuney.text or tuney.text_args)
        ):
            return
        try:
            data = read_file(self.path)
        except (OSError, ValueError) as error:
            report_error(f'Could not restore {self.path}: {error}')
            return
        while True:
            try:
                state.restore_data(data)
                return
            except ValidationError as error:
                report_error(f'Could not restore fields from {self.path}: {error}')
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
