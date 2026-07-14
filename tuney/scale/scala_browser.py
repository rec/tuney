from __future__ import annotations

import sys
import tomllib
from functools import cache
from pathlib import Path
from zipfile import ZipFile

from pydantic import BaseModel, Field

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
        node = self.node(prefix)
        if node.value is not None:
            return node.value
        for c in sorted(node.children):
            if value := node.children[c].first(''):
                return value
        return None

    def terminal(self, prefix: str) -> Ratios | None:
        return self.node(prefix).value

    def unique(self, prefix: str) -> tuple[str, Ratios] | None:
        matches = self.node(prefix)._matches(prefix, 2)
        return matches[0] if len(matches) == 1 else None

    def _matches(self, prefix: str, limit: int) -> list[tuple[str, Ratios]]:
        matches = [(prefix, self.value)] if self.value is not None else []
        for c in sorted(self.children):
            if len(matches) >= limit:
                return matches
            matches.extend(self.children[c]._matches(prefix + c, limit - len(matches)))
        return matches


@cache
def scala_trie() -> ScalaTrie:
    return build_trie(scala_scales())


@cache
def scala_scales() -> dict[str, Ratios]:
    path = scales_zip_path()
    with ZipFile(path) as archive:
        data = tomllib.loads(archive.read(SCALES_TOML).decode())
    return {k: Ratios.model_validate(v) for k, v in data.items()}


def build_trie(scales: dict[str, Ratios]) -> ScalaTrie:
    root = ScalaTrie()
    for key, value in scales.items():
        node = root
        for c in key:
            node = node.children.setdefault(c, ScalaTrie())
        node.value = value
    return root


def scales_zip_path() -> Path:
    for path in scales_zip_paths():
        if path.exists():
            return path
    raise FileNotFoundError(f'Could not find {SCALES_ZIP}')


def scales_zip_paths() -> list[Path]:
    paths = []
    if bundle_root := getattr(sys, '_MEIPASS', None):
        paths.append(Path(bundle_root) / SCALES_ZIP)
    paths.append(Path(__file__).resolve().parents[2] / SCALES_ZIP)
    return paths
