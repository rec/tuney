from __future__ import annotations

import time
from abc import ABC, abstractmethod
from functools import cached_property
from typing import override

import numpy as np
from pydantic import BaseModel, Field
from sounddevice import CallbackStop, OutputStream

from ..runnable import Runnable
from .concurrent import Stoppable
from .device import Device

MASTER_GAIN = 0.25


class Player(BaseModel, Runnable, ABC):
    stoppable: Stoppable = Field(default_factory=Stoppable)
    device: Device = Device()
    chunk_count: int = 0
    frame_count: int = 0
    frame_size: int = 0
    gain: float = 1.0

    @abstractmethod
    def _fill(self, out: np.ndarray) -> bool | None:
        pass

    def fill(self, out: np.ndarray, frame_size: int) -> bool | None:
        success = self._fill(out)
        out *= MASTER_GAIN * self.gain
        self.chunk_count += 1
        self.frame_size = frame_size
        self.frame_count += frame_size
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
            self.stop()
            while self.is_running:
                time.sleep(0.001)

    @cached_property
    def stream(self) -> OutputStream:
        return OutputStream(
            callback=self.callback,
            finished_callback=self.stoppable.stop,
            **self.device.model_dump(),
        )
