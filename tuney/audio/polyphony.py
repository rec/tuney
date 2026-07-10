from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ..config.display import Display, Numeric
from ..config.tyro_option import tyro_option


class Polyphony(BaseModel):
    # Divisor applied to mixed voices to provide polyphonic headroom
    headroom: Annotated[float, tyro_option(), Display(column=1, row=0), Numeric()] = (
        Field(4, gt=0)
    )

    # Maximum number of notes that can play simultaneously
    max_voices: Annotated[int, tyro_option(), Display(column=2, row=0), Numeric()] = (
        Field(32, gt=0)
    )
