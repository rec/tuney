from __future__ import annotations

from typing import Annotated

import numpy as np
import tyro
from pydantic import BaseModel

from ..named_enum import NamedEnum
from ..types import NoteNumber
from .scipy import sawtooth


def sine(out: np.ndarray, duty_cycle: float) -> np.ndarray:
    return np.sin(out, out=out)


def triangle(out: np.ndarray, duty_cycle: float) -> np.ndarray:
    out[:] = sawtooth(out, duty_cycle)
    return out


class Waveform(NamedEnum):
    sine = (sine,)
    triangle = (triangle,)


class Oscillator(BaseModel, frozen=True):
    # Waveform used to synthesize notes
    waveform: Annotated[Waveform, tyro.conf.arg(aliases=['-w'], prefix_name=False)] = (
        Waveform.triangle
    )

    # Number of waveform cycles per note period
    period: Annotated[
        float,
        tyro.conf.arg(name='oscillator-period', aliases=['-e'], prefix_name=False),
    ] = 1.0

    # Fraction of each waveform cycle before its falling edge
    duty_cycle: Annotated[float, tyro.conf.arg(aliases=['-u'], prefix_name=False)] = 0.5

    # Note number with no keyboard gain adjustment
    key_scale_note: Annotated[
        NoteNumber, tyro.conf.arg(aliases=['-K'], prefix_name=False)
    ] = 64

    # Gain octaves added per keyboard octave above key_scale_note
    key_scale: Annotated[float, tyro.conf.arg(aliases=['-k'], prefix_name=False)] = 0.0

    def __call__(self, start: float, length: int, period: float) -> np.ndarray:
        # TODO: add intensity to compensate for different energies
        end = start + length
        ratio = 2 * np.pi * self.period / period
        wave = np.linspace(start * ratio, end * ratio, length, endpoint=False)
        return self.waveform.value[0](wave, self.duty_cycle)

    def gain(self, note_number: NoteNumber) -> float:
        return 2 ** (self.key_scale * (note_number - self.key_scale_note) / 12)
