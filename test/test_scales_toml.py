from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

from tuney.scale.ratios import Ratios


def test_scales_toml_script_reads_scala_zip(tmp_path, monkeypatch) -> None:
    module = _build_scales_toml_module()
    zip_path = tmp_path / 'scales.zip'
    toml_path = tmp_path / 'scales.toml'
    with ZipFile(zip_path, 'w') as archive:
        archive.writestr(
            'scl/example.scl',
            '! example.scl\n!\nExample scale\n 2\n!\n 100.0\n 3/2\n\n',
        )

    monkeypatch.setattr(module, 'SCALES_ZIP', zip_path)
    monkeypatch.setattr(module, 'SCALES_TOML', toml_path)
    module.main()

    assert module.read_scales(zip_path) == {
        'example': Ratios(
            text='cents(100.0); 3/2',
            name='example.scl',
            desc='Example scale',
        )
    }
    assert tomllib.loads(toml_path.read_text()) == {
        'example': {
            'text': 'cents(100.0); 3/2',
            'name': 'example.scl',
            'desc': 'Example scale',
        }
    }


def _build_scales_toml_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / 'scala' / 'build_scales_toml.py'
    spec = importlib.util.spec_from_file_location('build_scales_toml', path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
