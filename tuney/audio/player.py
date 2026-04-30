from __future__ import annotations

import dataclasses as dc
from abc import ABC, abstractmethod
from functools import cached_property
from typing import override

import numpy as np
from sounddevice import CallbackStop, OutputStream

from ..runnable import Runnable
from . import apply_gain
from .concurrent import Stoppable
from .device import Device

MASTER_GAIN = 0.05


@dc.dataclass
class Player(Runnable, ABC):
    stoppable: Stoppable = dc.field(default_factory=Stoppable)
    device: Device = Device()
    frame_size: int = 0
    gain: float = 1.0

    chunk_count: dc.InitVar[int] = 0

    @abstractmethod
    def _fill(self, out: np.ndarray) -> bool | None:
        pass

    def fill(self, out: np.ndarray, frame_size: int) -> bool | None:
        if self.frame_size and frame_size != self.frame_size:
            # Hope this never happens
            print('framesize change', self.frame_size, frame_size)
        self.frame_size = frame_size
        success = self._fill(out)
        apply_gain(out, MASTER_GAIN * self.gain)
        self.chunk_count += 1
        return success

    def callback(
        self, out: np.ndarray, frame_size: int, time: float, status: str
    ) -> None:
        if status:
            print('Playback', status)  # TODO:

        if not self.fill(out, frame_size) or not self.is_running:
            self.stop()
            raise CallbackStop

    @override
    def _run(self):
        with self.stream:
            self.stoppable.wait()

    @cached_property
    def stream(self) -> OutputStream:
        return OutputStream(
            callback=self.callback,
            finished_callback=self.stoppable.stop,
            **self.device.model_dump(),
        )

    @property
    def frame_count(self) -> int:
        return self.frame_size * self.chunk_count
