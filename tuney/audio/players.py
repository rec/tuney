from __future__ import annotations

from typing import Any

import numpy as np

from .player import Player
from .sample_data import SampleData


class DataPlayer(Player):
    def __init__(self, sample_data: SampleData, **kwargs: Any) -> None:
        self.data = sample_data.data
        super().__init__(**kwargs)

    def _fill(self, out: np.ndarray) -> bool | None:
        d = self.data.data[self.frame_count : self.frame_count + self.frame_size]
        if out.shape and out.shape[1:] == (1,) and d.shape and len(d.shape) == 1:
            d = np.reshape(d, (*d.shape, 1))
        out[: len(d)] = d
        success = len(d) == self.frame_size
        if not success:
            out[len(d) : self.frame_size] = 0
        return success


class FilePlayer(DataPlayer):
    def __init__(self, filename: str, **kwargs: Any) -> None:
        super().__init__(SampleData.make(filename).cut_to(1.5), **kwargs)
