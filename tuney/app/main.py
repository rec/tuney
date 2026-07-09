import sys
from pathlib import Path

import tyro
from pydantic import BaseModel, ValidationError

from ..presets import merged_data, read_file, read_preset
from .app import App, run
from .platform_info import exit_with_message


def main() -> None:
    data = {}
    try:
        f = tyro.cli(App, prog='tuney')
        assert hasattr(f, 'config_file')
        assert hasattr(f, 'preset')
        if _startup_files_should_be_skipped(f):
            assert isinstance(f, BaseModel)
            f = f.model_copy(
                update={
                    'config_file': None,
                    'preset': None,
                    'skip_startup_files': True,
                }
            )
        elif f.config_file or f.preset:
            if f.preset:
                data = merged_data(data, read_preset(f.preset), {'preset': f.preset})
            if f.config_file:
                assert isinstance(f.config_file, Path)
                data = merged_data(data, read_file(f.config_file))
            f = tyro.cli(App, prog='tuney', default=App(**data))
        result = run(f)
    except (ValidationError, FileExistsError) as e:
        if getattr(locals().get('f'), 'verbose', False):
            raise
        result = e
    if result is None:
        sys.exit()
    exit_with_message(str(result))


def _startup_files_should_be_skipped(f: object) -> bool:
    if not getattr(f, 'gui', False):
        return False
    from ..ui.startup import startup_modifier_held

    return startup_modifier_held()
