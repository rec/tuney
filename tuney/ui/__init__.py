from __future__ import annotations

import dataclasses as dc
import math
from collections.abc import Sequence
from typing import NamedTuple


@dc.dataclass
class Text:
    labels: Sequence[str]
    on: bool = False


class ColumnsRows(NamedTuple):
    columns: int
    rows: int

    @staticmethod
    def from_length(n: int) -> ColumnsRows:
        c = int(math.ceil(n**0.5))
        r = n // c
        return ColumnsRows(c, r + (n > (r * c)))
