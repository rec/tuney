from __future__ import annotations

import dataclasses as dc
from abc import ABC, abstractmethod
from functools import cached_property
from threading import Event
from typing import override

from sounddevice import CallbackStop, OutputStream

from ..runnable import Runnable
from ..types import Data
from . import apply_gain
from .device_config import DeviceConfig

MASTER_GAIN = 0.1


@dc.dataclass
class Player(Runnable, ABC):
    config: DeviceConfig = dc.field(default_factory=DeviceConfig)

    chunk_count: int = 0
    frame_size: int = 0
    gain: float = 1.0

    _event: Event = dc.field(default_factory=Event)

    @abstractmethod
    def _fill(self, out: Data) -> bool:
        pass

    def fill(self, out: Data, frame_size: int) -> bool:
        if self.frame_size and frame_size != self.frame_size:
            # Hope this never happens
            print('framesize change', self.frame_size, frame_size)
        self.frame_size = frame_size
        success = self._fill(out)
        apply_gain(out, MASTER_GAIN * self.gain)
        self.chunk_count += 1
        return success

    def callback(self, out: Data, frame_size: int, time: float, status: str) -> None:
        if status:
            print('Playback', status)  # TODO:

        if not self.fill(out, frame_size) or not self.is_running:
            self.stop()
            raise CallbackStop

    @override
    def _run(self):
        with self.stream:
            self._event.wait()

    @cached_property
    def stream(self) -> OutputStream:
        callbacks = {'callback': self.callback, 'finished_callback': self._event.set}
        return OutputStream(**dc.asdict(self.config), **callbacks)

    @property
    def frame_count(self) -> int:
        return self.frame_size * self.chunk_count
