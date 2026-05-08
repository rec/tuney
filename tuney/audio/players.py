from __future__ import annotations

from typing import Any

import numpy as np

from .player import Player
from .sample_data import SampleData


class DataPlayer(Player):
    def __init__(self, sample_data: SampleData, **kwargs: Any) -> None:
        self.data = sample_data.data
        kwargs.setdefault('device', {})['samplerate'] = sample_data.samplerate
        super().__init__(**kwargs)

    def _fill(self, out: np.ndarray) -> bool | None:
        chunk = self.data.data[self.frame_count : self.frame_count + self.frame_size]
        out[: len(chunk)] = chunk
        success = len(chunk) == self.frame_size
        if not success:
            out[len(chunk) : self.frame_size] = 0
        return success


class FilePlayer(DataPlayer):
    def __init__(self, filename: str, **kwargs: Any) -> None:
        super().__init__(SampleData.make(filename).cut_to(1.5), **kwargs)
