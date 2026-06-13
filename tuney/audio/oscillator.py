from __future__ import annotations

from abc import abstractmethod
from typing import override

import numpy as np
from pydantic import BaseModel


class Oscillator(BaseModel, frozen=True):
    period: float = 2 * np.pi
    # TODO: add intensity to compensate for different energies

    @abstractmethod
    def function(self, x: np.ndarray, out: np.ndarray) -> np.ndarray: ...


class Sine(Oscillator):
    @override
    def function(self, x: np.ndarray, out: np.ndarray) -> np.ndarray:
        return np.sin(x, out=out)


class Triangle(Oscillator):
    width: float = 0.5

    @override
    def function(self, x: np.ndarray, out: np.ndarray) -> np.ndarray:
        from .scipy import sawtooth

        out[:] = sawtooth(x, self.width)
        return out


class OldSawtooth(Oscillator):
    @override
    def function(self, x: np.ndarray, out: np.ndarray) -> np.ndarray:
        return np.add(np.mod(x, 2.0, out=out), -1.0, out=out)


class Sawtooth(Triangle):
    width: float = 0


sawtooth, sine, triangle = Sawtooth(), Sine(), Triangle()
