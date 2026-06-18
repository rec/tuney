from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel

from .mixer import Mixer, NoteEvent


class OfflineRenderer(BaseModel):
    mixer: Mixer

    def apply(self, event: NoteEvent) -> bool:
        return self.mixer.apply(event)

    def stop_all(self) -> None:
        self.mixer.stop_all()

    def render(
        self,
        events: Sequence[NoteEvent],
        frame_size: int,
        dtype: DTypeLike = float,
    ) -> np.ndarray:
        for event in events:
            self.apply(event)
        return self.mixer.render(frame_size, dtype)
