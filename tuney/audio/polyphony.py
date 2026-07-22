from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ..config.display import Numeric
from ..config.tyro_option import tyro_option


class Polyphony(BaseModel):
    # Divisor applied to mixed voices to provide polyphonic headroom
    headroom: Annotated[
        float, tyro_option(), Numeric(column=1, row=0, width=5, decimals=0, inc=1)
    ] = Field(4, gt=0)

    # Maximum number of notes that can play simultaneously
    max_voices: Annotated[int, tyro_option(), Numeric(column=2, row=0, width=3)] = (
        Field(10, gt=0)
    )
