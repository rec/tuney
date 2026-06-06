from __future__ import annotations

from pydantic import BaseModel

from ..types import Milliseconds


class TimeData[Data](BaseModel, frozen=True):
    time: Milliseconds
    data: Data

    def __lt__(self, other: TimeData[Data]) -> bool:
        return self.time < other.time
