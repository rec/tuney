from __future__ import annotations

import dataclasses as dc
from abc import ABC, abstractmethod
from typing import Any, Callable, TypeAlias, override

import numpy as np

from . import Data, Number

Function: TypeAlias = Callable[..., Any]


class Oscillator:
    period: Number = 2 * np.pi
    # TODO: add intensity to compensate for different energies

    @abstractmethod
    def function(self, x: Data, out: Data) -> Data: ...



class Sine(Oscillator):
    @override
    def function(self, x: Data, out: Data) -> Data:
        return np.sin(x, out=out)


class Triangle(Oscillator):
    width: Number = 0.5

    @override
    def function(self, x: Data, out: Data) -> Data:
        from .scipy import sawtooth

        out[:] = sawtooth(x, self.width)
        return out


class OldSawtooth(Oscillator):
    @override
    def function(self, x: Data, out: Data) -> Data:
        return np.add(np.mod(x, 2.0, out=out), -1.0, out=out)


class Sawtooth(Triangle):
    width: Number = 0




sawtooth, sine, triangle = Sawtooth(), Sine(), Triangle()
