from __future__ import annotations

from functools import cached_property

import numpy as np
import soundfile
from pydantic import BaseModel, ConfigDict

from .device import Device


class SampleData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: np.ndarray
    sample_rate: int

    def device(self, device: int | str | None) -> Device:
        return Device(
            channels=self.channels,
            device=device,
            sample_rate=self.sample_rate,
        )

    @staticmethod
    def make(filename: str) -> SampleData:
        data, sample_rate = soundfile.read(filename, always_2d=True)
        return SampleData(data=data, sample_rate=sample_rate)

    def cut_to(self, time: float) -> SampleData:
        count = round(time * self.sample_rate)
        if (to_cut := len(self.data) - count) <= 0:
            return self
        half = to_cut // 2
        return SampleData(
            data=self.data[half : count + half], sample_rate=self.sample_rate
        )

    @cached_property
    def channels(self) -> int:
        return self.data.shape[1]
