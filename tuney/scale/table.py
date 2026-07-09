from __future__ import annotations

from functools import cached_property
from typing import Annotated

from pydantic import BaseModel

from ..cfg.display import Display
from ..cfg.tyro_option import tyro_option
from . import Number, evaluate

type Frequency = float  # Must be non-negative


class Table(BaseModel, frozen=True):
    #: Absolute frequency expressions, indexed by note number
    text: Annotated[str, tyro_option(), Display(row=0, width=24)] = ''

    def __call__(self, note_delta: int) -> Frequency:
        return self.values[note_delta % len(self.values)]

    @cached_property
    def values(self) -> list[Frequency]:
        return [float(i) for i in _evaluate_text(self.text)]


def _evaluate_text(text: str) -> list[Number]:
    return evaluate.evaluate_all(i.strip() for i in text.split(';') if i.strip())
