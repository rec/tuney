from __future__ import annotations

import enum

import numpy as np
from pydantic import BaseModel

from .scipy import sawtooth


def sine(out: np.ndarray, duty_cycle: float) -> np.ndarray:
    return np.sin(out, out=out)


def triangle(out: np.ndarray, duty_cycle: float) -> np.ndarray:
    out[:] = sawtooth(out, duty_cycle)
    return out


class Waveform(enum.Enum):
    sine = (sine,)
    triangle = (triangle,)

    @classmethod
    def _missing_(cls, value: object) -> Waveform | None:
        return (
            cls[value] if isinstance(value, str) and value in cls.__members__ else None
        )


class Oscillator(BaseModel, frozen=True):
    waveform: Waveform = Waveform.triangle
    period: float = 1.0
    duty_cycle: float = 0.5

    def __call__(self, start: float, length: int, period: float) -> np.ndarray:
        # TODO: add intensity to compensate for different energies
        end = start + length
        ratio = 2 * np.pi * self.period / period
        wave = np.linspace(start * ratio, end * ratio, length, endpoint=False)
        return self.waveform.value[0](wave, self.duty_cycle)
