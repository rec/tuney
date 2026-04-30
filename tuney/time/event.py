from __future__ import annotations

import dataclasses as dc

from ..types import Milliseconds


@dc.dataclass  # OK
class Event[Data]:
    timestamp: Milliseconds
    data: Data

    def __lt__(self, other: Event[Data]) -> bool:
        return self.timestamp < other.timestamp
