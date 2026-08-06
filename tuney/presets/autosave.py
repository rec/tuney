from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from ..app.platform_info import app_state_dir
from ..ui.startup import startup_modifier_held
from .preset import read_file

if TYPE_CHECKING:
    from ..app.app import App
    from ..ui.history import LoopState, WindowState

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
        loop_state, loop_error = _loop_state(data.pop('loop', None))
        window_state, window_error = _window_state(data.pop('window', None))
        if data.get('load_autosave') is False:
            state.restore_data({'gui': state.gui, 'load_autosave': False})
            if loop_state is not None:
                state.__dict__['_autosave_loop_state'] = loop_state
            if window_state is not None:
                state.__dict__['_autosave_window_state'] = window_state
            return loop_error or window_error
        restore_error: ValidationError | None = None
        while True:
            try:
                state.restore_data(data)
                if loop_state is not None:
                    state.__dict__['_autosave_loop_state'] = loop_state
                if window_state is not None:
                    state.__dict__['_autosave_window_state'] = window_state
                if restore_error is None:
                    return loop_error or window_error
                if loop_error is not None or window_error is not None:
                    return loop_error or window_error
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


def _loop_state(data: object) -> tuple[LoopState | None, AutosaveRestoreError | None]:
    if data is None:
        return None, None
    from ..ui.history import LoopState

    try:
        return LoopState.model_validate(data), None
    except ValidationError as error:
        return None, AutosaveRestoreError(f'Could not restore loop state: {error}')


def _window_state(
    data: object,
) -> tuple[WindowState | None, AutosaveRestoreError | None]:
    if data is None:
        return None, None
    from ..ui.history import WindowState

    try:
        return WindowState.model_validate(data), None
    except ValidationError as error:
        return None, AutosaveRestoreError(f'Could not restore window state: {error}')


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
