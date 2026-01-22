from __future__ import annotations

import dataclasses as dc
from abc import ABC, abstractmethod
from typing import Any, Callable, TypeAlias, override

import numpy as np

from . import Data, Number

Function: TypeAlias = Callable[..., Any]


class Oscillator:
    period: Number = 2 * np.pi

    def function(self, x: Data, out: Data) -> Data:
        return np.sin(x, out=out)
