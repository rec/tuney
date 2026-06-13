from __future__ import annotations

from abc import abstractmethod
from typing import override

import numpy as np
from pydantic import BaseModel


class Oscillator(BaseModel, frozen=True):
    period: float = 2 * np.pi
    # TODO: add intensity to compensate for different energies

    def __call__(self, start: float, length: int, period: float) -> np.ndarray:
        end = start + length
        ratio = self.period / period
        wave = np.linspace(start * ratio, end * ratio, length, endpoint=False)
        return self.function(wave, out=wave)

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


class Sawtooth(Triangle):
    width: float = 0
