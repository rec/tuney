from __future__ import annotations

from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, model_validator

from ..app.platform_info import report_error
from ..config.display import Display
from ..config.text_file import read_text_file
from ..config.tyro_option import tyro_option
from . import Number, evaluate, uncents


class Ratios(BaseModel):
    #: Ratio expressions for each step in the scale
    text: Annotated[str, tyro_option(), Display(row=0, width=24)] = ''

    #: Name of this ratio scale
    name: Annotated[str, tyro_option(), Display(row=1, column=0)] = ''

    #: Description of this ratio scale
    desc: Annotated[str, tyro_option(), Display(row=1, column=1, width=24)] = ''

    @model_validator(mode='after')
    def _validate_text(self) -> Ratios:
        if not _split_expression_text(self.text):
            raise ValueError('No tuning ratios configured')
        return self

    def __call__(self, note_delta: int) -> Number:
        # Returns a frequency ratio
        ratios = self.ratios
        d, m = divmod(note_delta, len(ratios))
        return ratios[-1] ** d * (ratios[m - 1] if m else 1)

    @cached_property
    def length(self) -> int:
        return len(self.ratios)

    @cached_property
    def ratios(self) -> list[Number]:
        ratios = evaluate.evaluate_all(_split_expression_text(self.text))
        if any(i <= 0 for i in ratios):
            raise ValueError('Tuning ratios must be positive')
        return ratios

    @staticmethod
    def read_scala_file(path: Path, name: str = '') -> Ratios:
        lines = read_text_file(path).splitlines()
        desc, length, *names = (i.strip() for i in lines if not i.startswith('!'))

        if int(length) != len(names):
            report_error(f'In file {path}: {length=} != {len(names)=}')

        it = (s[0] for n in names if (s := n.split()))
        text = '; '.join(f'cents({s})' if '.' in s else s for s in it)
        return Ratios(text=text, name=name or path.name, desc=desc)

    @staticmethod
    def from_strings(strings: Iterable[str], name: str = '', desc: str = '') -> Ratios:
        return Ratios(text='; '.join(strings), name=name, desc=desc)

    def write_scala_file(self, path: Path, encoding='latin-1') -> None:
        with path.open('w', encoding=encoding) as fp:
            _ = self.length
            fp.write(SCALA_TEMPLATE.format(**self.__dict__))
            for r in self.ratios:
                s = f'{uncents(r):.6f}' if isinstance(r, float) else str(r)
                fp.write(f' {s}\n')


def _split_expression_text(text: str) -> list[str]:
    return [s for i in text.split(';') if (s := i.strip())]


SCALA_TEMPLATE = """\
! {name}
!
{desc}
 {length}
!
"""
