from __future__ import annotations

from typing import Annotated

import numpy as np
from enge.synth import waveform_samples
from pydantic import Field
from reccy.configuration.tyro import tyro_option
from ufor import oscillator
from ufor.number import NoteNumber
from ufor.oscillator import Waveform

from ..config.annotations import Beginner, Display, Numeric


class Oscillator(oscillator.Oscillator, frozen=False):
    # Waveform used to synthesize notes
    waveform: Annotated[Waveform, tyro_option('-w'), Beginner, Display(row=0)] = (
        Waveform.triangle
    )

    # Fraction of each waveform cycle before its falling edge
    duty_cycle: Annotated[
        float,
        tyro_option('-u'),
        Numeric(column=1, row=0, min=0, max=1.0, dial=True, inc=0.01),
    ] = Field(0.5, ge=0, le=1)

    # Note number with no keyboard gain adjustment
    key_scale_note: Annotated[
        NoteNumber, tyro_option('-K'), Numeric(column=2, row=0, min=0, max=127, width=3)
    ] = Field(64, ge=0, le=127)

    # Gain decibels added per keyboard octave above key_scale_note
    key_scale: Annotated[
        float, tyro_option('-k'), Numeric(column=3, row=0, width=5)
    ] = 0.0

    def __call__(
        self, start: float | np.ndarray, length: int, period: float | np.ndarray
    ) -> np.ndarray:
        return waveform_samples(self, start, length, period)
