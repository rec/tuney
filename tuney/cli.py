import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import tyro
from pydantic import ValidationError
from typing_extensions import TypeIs


def is_str_dict(x: Any) -> TypeIs[dict[str, Any]]:
    return isinstance(x, dict) and all(isinstance(k, str) for k in x.keys())


def read_file(path: Path) -> dict[str, Any]:
    data = path.read_text()
    match path.suffix:
        case '.toml':
            result = tomllib.loads(data)
        case '.json':
            result = json.loads(data)
        case _:
            raise ValueError(f'Do not understand file {path}')
    if not is_str_dict(result):
        raise ValueError(f'File {path} does not contain a string dictionary')
    return result


def cli(cls, prog: str):
    try:
        f = tyro.cli(cls, prog=prog)
        assert hasattr(f, 'config_file')
        if f.config_file:
            assert isinstance(f.config_file, Path)
            default = cls(**read_file(f.config_file))
            f = tyro.cli(cls, prog=prog, default=default)
        assert callable(f), f
        result = f()
    except (ValidationError, FileExistsError) as e:
        if getattr(locals().get('f'), 'verbose', False):
            raise
        result = e
    sys.exit(str(result))
