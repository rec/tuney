from __future__ import annotations

import numpy as np
import dataclasses as dc
from . import Function, Number


@dc.dataclass(frozen=True)
class Oscillator:
    function: Function = np.sin
    period: Number = 2 * np.pi
