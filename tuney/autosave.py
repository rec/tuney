from __future__ import annotations

import os
import sys
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from .presets import read_file

if TYPE_CHECKING:
    from .tuney import Tuney

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

    def restore_if(self, tuney: Tuney) -> None:
        self.restore(
            self.should_restore(
                gui=tuney.gui,
                config_file=tuney.config_file,
                preset=tuney.preset,
                text=tuney.text,
                text_args=tuney.text_args,
            ),
            tuney.restore_data,
        )

    def should_restore(
        self,
        *,
        gui: bool,
        config_file: Path | None,
        preset: str | None,
        text: object,
        text_args: list[str],
    ) -> bool:
        return (
            gui
            and config_file is None
            and preset is None
            and text is None
            and not text_args
        )

    def restore(
        self,
        should_restore: bool,
        restore_data: Callable[[dict[str, object]], None],
    ) -> None:
        if not should_restore or not self.path.exists():
            return
        try:
            data = read_file(self.path)
        except (OSError, ValueError) as error:
            print(f'Could not restore {self.path}: {error}', file=sys.stderr)
            return
        self.restore_data(data, restore_data)

    def restore_data(
        self,
        data: dict[str, object],
        restore_data: Callable[[dict[str, object]], None],
    ) -> None:
        while True:
            try:
                restore_data(data)
                return
            except ValidationError as error:
                print(
                    f'Could not restore fields from {self.path}: {error}',
                    file=sys.stderr,
                )
                if not any(_delete_data_path(data, e['loc']) for e in error.errors()):
                    return


def _delete_data_path(data: dict[str, object], loc: tuple[object, ...]) -> bool:
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
