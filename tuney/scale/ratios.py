from __future__ import annotations

from collections.abc import Iterable, Sequence
from fractions import Fraction
from functools import cache, cached_property
from pathlib import Path

from pydantic import BaseModel

from ..platform_info import report_error
from ..text_file import read_text_file
from . import evaluate, uncents


class Ratios(BaseModel, frozen=True):
    ratios: Sequence[float | Fraction] = ()
    name: str = ''
    desc: str = ''

    @cache  # noqa: B019
    def __getitem__(self, steps: int) -> float | Fraction:
        d, m = divmod(steps, self.length)
        return self.ratios[-1] ** d * (self.ratios[m - 1] if m else 1)

    @cached_property
    def length(self) -> int:
        return 1 + len(self.ratios)

    @staticmethod
    def read_scala_file(path: Path, name: str = '') -> Ratios:
        lines = read_text_file(path).splitlines()
        desc, length, *names = (i.strip() for i in lines if not i.startswith('!'))

        if int(length) != len(names):
            report_error(f'In file {path}: {length=} != {len(names)=}')

        it = (s[0] for n in names if (s := n.split()))
        ratios = [evaluate.cents(float(s)) if '.' in s else Fraction(s) for s in it]
        return Ratios(ratios=ratios, name=name or path.name, desc=desc)

    @staticmethod
    def from_strings(strings: Iterable[str], name: str = '', desc: str = '') -> Ratios:
        ratios = evaluate.evaluate_all(strings)
        return Ratios(ratios=ratios, name=name, desc=desc)

    def write_scala_file(self, path: Path, encoding='latin-1') -> None:
        with path.open('w', encoding=encoding) as fp:
            _ = self.length
            fp.write(SCALA_TEMPLATE.format(**self.__dict__))
            for r in self.ratios:
                s = f'{uncents(r):.6}' if isinstance(r, float) else str(r)
                fp.write(f' {s}\n')


SCALA_TEMPLATE = """\
! {name}
!
{desc}
 {length}
!
"""
