from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel

from .mixer import Mixer, NotePress


class OfflineRenderer(BaseModel):
    mixer: Mixer

    def apply(self, note: NotePress) -> bool:
        return self.mixer.apply(note)

    def stop_all(self) -> None:
        self.mixer.stop_all()

    def render(
        self,
        notes: Sequence[NotePress],
        frame_size: int,
        dtype: DTypeLike = float,
    ) -> np.ndarray:
        for event in notes:
            self.apply(event)
        return self.mixer.render(frame_size, dtype)
