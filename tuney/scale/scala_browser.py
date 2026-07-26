from __future__ import annotations

import sys
import tomllib
from functools import cache
from pathlib import Path
from zipfile import ZipFile

from pydantic import BaseModel, Field

from ..app.platform_info import instrument
from .ratios import Ratios

SCALES_ZIP = Path('scala/scales.toml.zip')
SCALES_TOML = 'scales.toml'


class ScalaTrie(BaseModel):
    children: dict[str, ScalaTrie] = Field(default_factory=dict)
    value: Ratios | None = None

    def choices(self, prefix: str) -> list[str]:
        return sorted(self.node(prefix).children)

    def node(self, prefix: str) -> ScalaTrie:
        node = self
        for c in prefix:
            node = node.children[c]
        return node

    def first(self, prefix: str) -> Ratios | None:
        if match := self.first_match(prefix):
            return match[1]
        return None

    def first_match(self, prefix: str) -> tuple[str, Ratios] | None:
        return self.node(prefix)._first_match(prefix)

    def _first_match(self, prefix: str) -> tuple[str, Ratios] | None:
        if self.value is not None:
            return prefix, self.value
        for c in sorted(self.children):
            if value := self.children[c]._first_match(prefix + c):
                return value
        return None

    def terminal(self, prefix: str) -> Ratios | None:
        return self.node(prefix).value


@cache
def scala_trie() -> ScalaTrie:
    instrument('scala trie build start')
    return build_trie(scala_scales())


@cache
def scala_scales() -> dict[str, Ratios]:
    path = scales_zip_path()
    instrument('scala scales load start', path=path)
    with ZipFile(path) as archive:
        data = tomllib.loads(archive.read(SCALES_TOML).decode())
    scales = {k: Ratios.model_validate(v) for k, v in data.items()}
    instrument('scala scales load end', count=len(scales))
    return scales


def build_trie(scales: dict[str, Ratios]) -> ScalaTrie:
    root = ScalaTrie()
    for value in scales.values():
        node = root
        for c in value.name.casefold():
            node = node.children.setdefault(c, ScalaTrie())
        node.value = value
    instrument('scala trie build end', count=len(scales))
    return root


def scales_zip_path() -> Path:
    for path in scales_zip_paths():
        if path.is_file():
            return path
        if path.is_dir() and (nested := path / SCALES_ZIP.name).is_file():
            return nested
    raise FileNotFoundError(f'Could not find {SCALES_ZIP}')


def scales_zip_paths() -> list[Path]:
    paths = []
    if bundle_root := getattr(sys, '_MEIPASS', None):
        paths.append(Path(bundle_root) / SCALES_ZIP)
    paths.append(Path(__file__).resolve().parents[2] / SCALES_ZIP)
    return paths
