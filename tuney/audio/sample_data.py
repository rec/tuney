from __future__ import annotations

import dataclasses as dc
from functools import cached_property
from typing import TypeAlias

import soundfile

from .device_config import DeviceConfig

import numpy as np

Data: TypeAlias = np.ndarray


@dc.dataclass
class SampleData:
    data: Data
    samplerate: int

    def config(self, device: int | str | None) -> DeviceConfig:
        return DeviceConfig(
            channels=self.channels, device=device, samplerate=self.samplerate
        )

    @staticmethod
    def make(filename: str) -> SampleData:
        return SampleData(*soundfile.read(filename, always_2d=True))

    def cut_to(self, time: float) -> SampleData:
        count = round(time * self.samplerate)
        to_cut = len(self.data) - count
        if to_cut <= 0:
            return self
        half = to_cut // 2
        return SampleData(self.data[half : count + half], self.samplerate)

    @cached_property
    def channels(self) -> int:
        return self.data.shape[1]
