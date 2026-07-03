from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ..display import Display
from ..tyro_option import tyro_option


class Polyphony(BaseModel, frozen=True):
    # Divisor applied to mixed voices to provide polyphonic headroom
    headroom: Annotated[float, tyro_option(), Display(row=0, order=1)] = Field(
        4, gt=0
    )

    # Maximum number of notes that can play simultaneously
    max_voices: Annotated[int, tyro_option(), Display(row=0, order=2)] = Field(
        32, gt=0
    )
