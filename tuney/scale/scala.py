from __future__ import annotations

import sys
from fractions import Fraction
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel

# See https://www.huygens-fokker.org/scala/scl_format.html

EPSILON = 3e-6
LIMIT = 13
ADJUST = False


class Power(BaseModel, frozen=True):
    base: float | Fraction
    power: float | Fraction

    @cached_property
    def value(self) -> float | Fraction:
        return type(self.base)(self.base**self.power)


class Scala(BaseModel, frozen=True):
    pitches: list[float | Fraction | tuple[Fraction]]
    description: str = ''

    @staticmethod
    def make(path: Path) -> Scala:
        with path.open(encoding='latin-1') as fp:
            desc, length, *names = (i.strip() for i in fp if not i.startswith('!'))
        if int(length) != len(names):
            print(f'{length=} != {len(names)=}', file=sys.stderr)

        pitches = [to_pitch(p) for p in names if p.strip()]
        return Scala(description=desc, pitches=pitches)


def to_pitch(s: str, adjust: bool = False) -> float | Fraction:
    s = s.split()[0]  # Doesn't fully comply but seems to work
    if '.' not in s:
        return Fraction(s)

    cents = float(s)
    if adjust and (f := perhaps_round(cents)) is not None:
        # Correct numbers are very close to small fractions like 257.14286
        # but this code is wrong.
        cents = f
    return 2 ** (cents / 1200)


def perhaps_round(f: float) -> float | None:
    fr = float(Fraction(f).limit_denominator(LIMIT))
    if abs(f - fr) < EPSILON:
        return fr


def read_all(path: Path) -> dict[str, Scala]:
    return {p.stem: Scala.make(p) for p in path.glob('*.scl')}
