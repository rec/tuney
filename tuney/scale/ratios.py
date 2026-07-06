from __future__ import annotations

from fractions import Fraction
from functools import cache
from collections.abc import Sequence

from .evaluate import cents

from pydantic import BaseModel


class Ratios(BaseModel, frozen=True):
    ratios: Sequence[float]

    @cache
    def __getitem__(self, steps: int) -> float:
        L = len(self.ratios) + 1
        d, m = divmod(steps, L)
        return self.ratios[-1]**d * (self.ratios[m - 1] if m else 1)

    @staticmethod
    def from_scala(



def _scala_line(s: str) -> float | Fraction:
    if not (s := (s.split() or [''])[0]):
        raise ValueError('Empty string')
    return cents(float(s)) if '.' in s else Fraction(s)
