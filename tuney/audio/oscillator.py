from __future__ import annotations

import dataclasses as dc
from typing import Any, Callable, TypeAlias

import numpy as np

from . import Number

Function: TypeAlias = Callable[..., Any]


@dc.dataclass(frozen=True)
class Oscillator:
    function: Function = np.sin
    period: Number = 2 * np.pi
