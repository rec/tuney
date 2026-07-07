from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ..display import Beginner, Dial, Display, General
from ..scale import NoteNumber
from ..scale.scale import Scale
from ..scale.tuning import Tuning
from ..tyro_option import tyro_option
from .oscillator import Oscillator
from .polyphony import Polyphony


class Sound(BaseModel, frozen=True):
    # Synthesizer oscillator settings
    oscillator: Oscillator = Oscillator()

    # Map note numbers to note names and tuning positions
    scale: Scale = Scale()

    # The tuning used to convert note numbers into frequencies
    tuning: Tuning = Tuning()

    # Audio output gain
    gain: Annotated[
        float,
        tyro_option('-G'),
        General,
        Beginner,
        Display(step=0.01),
        Dial(max=2.0),
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
