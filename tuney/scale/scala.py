from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

from pydantic import BaseModel

from ..platform_info import report_error

# See https://www.huygens-fokker.org/scala/scl_format.html

EPSILON = 3e-6
LIMIT = 13
ADJUST = False


"""
10 / 2 ^ 3.0 / 4 cents
10/2^3.0/4 cents
"""

OTHER_RE = re.compile(r'[^^/.0-9\s]')


def scala_str_to_frequency_ratio(s: str, extended: bool = False) -> float:
    if m := OTHER_RE.search(s):
        s = s[: m.start()]

    base, _, exp = s.partition('^')
    if not (base := base.strip()):
        raise ValueError('Empty scala string')
    if '^' in exp:
        raise ValueError(f'String "{s}" has two or more ^ symbols')
    if exp and not extended:
        raise ValueError(f'String "{s}" has a ^ symbol')

    if extended:
        exp = (exp.split() or [''])[0] or '1'
    elif exp:
        raise ValueError(f'String "{s}" has a ^ symbol')

    result = Fraction(base) ** Fraction(exp)
    return 2 ** (result / 1200) if '.' in s else result


class Scala(BaseModel, frozen=True):
    frequencies: list[float]
    description: str = ''

    @staticmethod
    def make(path: Path) -> Scala:
        with path.open(encoding='latin-1') as fp:
            desc, length, *names = (i.strip() for i in fp if not i.startswith('!'))
        if int(length) != len(names):
            report_error(f'{length=} != {len(names)=}')

        freq = [scala_str_to_frequency_ratio(p) for p in names if p.strip()]
        return Scala(frequencies=freq, description=desc)
