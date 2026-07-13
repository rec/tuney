from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from ..app.platform_info import app_state_dir
from ..ui.startup import startup_modifier_held
from . import read_file

if TYPE_CHECKING:
    from ..app.app import App

AUTOSAVE_FILE = Path('tuney') / 'state.toml'


class AutosaveRestoreError(ValueError):
    pass


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

    def restore(self, state: App) -> Exception | None:
        if not (
            state.gui
            and state.load_autosave
            and not startup_modifier_held()
            and self.path.exists()
            and not (state.config_file or state.preset or state.text or state.text_args)
        ):
            return None
        try:
            data = read_file(self.path)
        except (OSError, ValueError) as error:
            return AutosaveRestoreError(f'Could not restore {self.path}: {error}')
        if data.get('load_autosave') is False:
            from ..app.app import restore_data

            restore_data(state, {'gui': state.gui, 'load_autosave': False})
            return None
        restore_error: ValidationError | None = None
        while True:
            try:
                from ..app.app import restore_data

                restore_data(state, data)
                if restore_error is None:
                    return None
                return AutosaveRestoreError(
                    f'Could not restore fields from {self.path}: {restore_error}'
                )
            except ValidationError as error:
                if restore_error is None:
                    restore_error = error
                if not any(_delete_data_path(data, e['loc']) for e in error.errors()):
                    return AutosaveRestoreError(
                        f'Could not restore fields from {self.path}: {error}'
                    )


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
