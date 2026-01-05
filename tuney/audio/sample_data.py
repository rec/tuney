from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from typing import TypeAlias

import soundfile
import numpy as np

Data: TypeAlias = np.ndarray


@dc.dataclass
class SampleData:
    data: Data
    sample_rate: int

    @staticmethod
    def make(filename: str) -> SampleData:
        return SampleData(*soundfile.read(filename, always_2d=True))

    def cut_to(self, time: float) -> SampleData:
        count = round(time * self.sample_rate)
        to_cut = len(self.data) - count
        if to_cut <= 0:
            return self
        half = to_cut // 2
        return SampleData(self.data[half : count + half], self.sample_rate)

    @cached_property
    def channels(self) -> int:
        return self.data.shape[1]
