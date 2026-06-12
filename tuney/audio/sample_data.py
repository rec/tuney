from __future__ import annotations

from functools import cached_property

import numpy as np
import soundfile
from pydantic import BaseModel, ConfigDict

from .device import Device


class SampleData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: np.ndarray
    samplerate: int

    def device(self, device: int | str | None) -> Device:
        return Device(channels=self.channels, device=device, samplerate=self.samplerate)

    @staticmethod
    def make(filename: str) -> SampleData:
        data, samplerate = soundfile.read(filename, always_2d=True)
        return SampleData(data=data, samplerate=samplerate)

    def cut_to(self, time: float) -> SampleData:
        count = round(time * self.samplerate)
        to_cut = len(self.data) - count
        if to_cut <= 0:
            return self
        half = to_cut // 2
        return SampleData(
            data=self.data[half : count + half], samplerate=self.samplerate
        )

    @cached_property
    def channels(self) -> int:
        return self.data.shape[1]
