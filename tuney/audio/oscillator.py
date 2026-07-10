from __future__ import annotations

from typing import Annotated

import numpy as np
from pydantic import BaseModel

from ..cfg.display import Beginner, Display, Numeric
from ..cfg.named_enum import NamedEnum
from ..cfg.tyro_option import tyro_option
from ..scale import NoteNumber
from .scipy import sawtooth
from .scipy import square as scipy_square


def sine(out: np.ndarray, duty_cycle: float) -> np.ndarray:
    return np.sin(out, out=out)


def triangle(out: np.ndarray, duty_cycle: float) -> np.ndarray:
    out[:] = sawtooth(out, duty_cycle)
    return out


def square(out: np.ndarray, duty_cycle: float) -> np.ndarray:
    out[:] = scipy_square(out, duty_cycle)
    return out


class Waveform(NamedEnum):
    sine = (sine,)
    square = (square,)
    triangle = (triangle,)


class Oscillator(BaseModel, frozen=True):
    # Waveform used to synthesize notes
    waveform: Annotated[Waveform, tyro_option('-w'), Beginner, Display(row=0)] = (
        Waveform.triangle
    )

    # Fraction of each waveform cycle before its falling edge
    duty_cycle: Annotated[
        float,
        tyro_option('-u'),
        Display(column=1, row=0),
        Numeric(min=0, max=1.0, dial=True),
    ] = 0.5

    # Note number with no keyboard gain adjustment
    key_scale_note: Annotated[
        NoteNumber, tyro_option('-K'), Display(column=2, row=0), Numeric()
    ] = 64

    # Gain decibels added per keyboard octave above key_scale_note
    key_scale: Annotated[
        float, tyro_option('-k'), Display(column=3, row=0), Numeric()
    ] = 0.0

    def __call__(self, start: float, length: int, period: float) -> np.ndarray:
        # TODO: add intensity to compensate for different energies
        end = start + length
        ratio = 2 * np.pi / period
        wave = np.linspace(start * ratio, end * ratio, length, endpoint=False)
        return self.waveform.value[0](wave, self.duty_cycle)

    def gain(self, note_number: NoteNumber) -> float:
        return 10 ** (self.key_scale * (note_number - self.key_scale_note) / 12 / 20)
