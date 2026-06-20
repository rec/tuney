import sys
from pathlib import Path

import tyro
from pydantic import ValidationError

from .presets import merged_data, read_file, read_preset


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
        assert callable(f), f
        result = f()
    except (ValidationError, FileExistsError) as e:
        if getattr(locals().get('f'), 'verbose', False):
            raise
        result = e
    sys.exit(result if result is None else str(result))
