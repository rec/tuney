from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ..display import Beginner, Display, General, Numeric
from ..scale import NoteNumber
from ..tyro_option import tyro_option
from .oscillator import Oscillator
from .polyphony import Polyphony


class Sound(BaseModel, frozen=True):
    # Synthesizer oscillator settings
    oscillator: Oscillator = Oscillator()

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
    ] = 44

    polyphony: Polyphony = Polyphony()

    # Minimum duration of each synthesized note, in seconds
    minimum_note_time: Annotated[float, tyro_option('-N'), Beginner, Display(row=0)] = (
        Field(0.5, ge=0)
    )

    def note_gain(self, note_number: NoteNumber) -> float:
        return self.gain * self.oscillator.gain(note_number)
