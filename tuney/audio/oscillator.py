from __future__ import annotations

from typing import Annotated

import numpy as np
from pydantic import BaseModel

from ..display import Beginner, Dial, Display
from ..named_enum import NamedEnum
from ..scale import NoteNumber
from ..tyro_option import tyro_option
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
    waveform: Annotated[Waveform, tyro_option('-w'), Beginner, Display(row=0)] = (
        Waveform.triangle
    )

    # Number of waveform cycles per note period
    period: Annotated[
        float,
        tyro_option('-e'),
        Beginner,
        Display(column=1, row=0),
        Dial(),
    ] = 1.0

    # Fraction of each waveform cycle before its falling edge
    duty_cycle: Annotated[
        float,
        tyro_option('-u'),
        Beginner,
        Display(column=2, row=0),
        Dial(max=1.0),
    ] = 0.5

    # Note number with no keyboard gain adjustment
    key_scale_note: Annotated[
        NoteNumber, tyro_option('-K'), Display(column=3, row=0)
    ] = 64

    # Gain octaves added per keyboard octave above key_scale_note
    key_scale: Annotated[float, tyro_option('-k'), Display(column=4, row=0)] = 0.0

    def __call__(self, start: float, length: int, period: float) -> np.ndarray:
        # TODO: add intensity to compensate for different energies
        end = start + length
        ratio = 2 * np.pi * self.period / period
        wave = np.linspace(start * ratio, end * ratio, length, endpoint=False)
        return self.waveform.value[0](wave, self.duty_cycle)

    def gain(self, note_number: NoteNumber) -> float:
        return 2 ** (self.key_scale * (note_number - self.key_scale_note) / 12)
