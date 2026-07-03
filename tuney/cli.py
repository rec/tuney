import sys
from pathlib import Path
from typing import Any

import tyro
from pydantic import ValidationError

from .app_state import exit_with_message
from .presets import merged_data, read_file, read_preset


def unprefixed_arg(**kwargs: Any) -> Any:
    return tyro.conf.arg(prefix_name=False, **kwargs)


def cli(cls, prog: str):
    try:
        f = tyro.cli(cls, prog=prog)
        assert hasattr(f, 'config_file')
        assert hasattr(f, 'preset')
        if f.config_file or f.preset:
            data = {}
            if f.preset:
                data = merged_data(data, read_preset(f.preset), {'preset': f.preset})
            if f.config_file:
                assert isinstance(f.config_file, Path)
                data = merged_data(data, read_file(f.config_file))
            default = cls(**data)
            f = tyro.cli(cls, prog=prog, default=default)
        result = f.state()
    except (ValidationError, FileExistsError) as e:
        if getattr(locals().get('f'), 'verbose', False):
            raise
        result = e
    if result is None:
        sys.exit()
    exit_with_message(str(result))
