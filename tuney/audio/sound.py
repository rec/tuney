from __future__ import annotations

from typing import Annotated

import tyro
from pydantic import BaseModel, Field

from ..config.display import Beginner, Display, General, Hidden, Numeric
from ..config.tyro_option import tyro_option
from ..scale import NoteNumber
from .oscillator import Oscillator
from .polyphony import Polyphony


class Sound(BaseModel):
    # Synthesizer oscillator settings
    oscillator: Oscillator = Field(default_factory=Oscillator)

    # Use the same time origin for every oscillator
    synchronize_oscillators: Annotated[
        bool, tyro_option('-F', name='synchronize-oscillators'), General, Beginner
    ] = False

    # Overall playback volume
    master_gain: Annotated[
        tyro.conf.Suppress[float],
        Hidden,
        Numeric(min=0, max=2.0, dial=True, inc=0.01),
    ] = Field(1.0, ge=0)

    # Audio output gain
    gain: Annotated[
        float,
        tyro_option('-G'),
        General,
        Beginner,
        Numeric(min=0, max=2.0, dial=True, inc=0.01),
    ] = 1.0

    # Offset added to generated note numbers before tuning
    note_offset: Annotated[
        NoteNumber,
        tyro_option('-n', name='audio-note-offset'),
        General,
        Beginner,
        Numeric(min=-99, max=99, width=3),
    ] = Field(44, ge=-99, le=99)

    polyphony: Polyphony = Field(default_factory=Polyphony)

    # Minimum duration of each synthesized note, in seconds
    minimum_note_time: Annotated[
        float, tyro_option('-N'), Beginner, Display(row=0), Numeric()
    ] = Field(0.5, ge=0)

    def note_gain(self, note_number: NoteNumber) -> float:
        return self.gain * self.oscillator.gain(note_number)
