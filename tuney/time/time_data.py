from __future__ import annotations

import dataclasses as dc

from ..types import Milliseconds


@dc.dataclass
class TimeData[Data]:
    time: Milliseconds
    data: Data

    def __lt__(self, other: TimeData[Data]) -> bool:
        return self.time < other.time
