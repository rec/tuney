from __future__ import annotations

import dataclasses as dc
from abc import ABC, abstractmethod
from functools import cached_property

from .device_config import DeviceConfig
from .playback import Data, Playback


@dc.dataclass
class Player(ABC):
    config: DeviceConfig = dc.field(default_factory=DeviceConfig)

    _chunk_count: int = 0
    _frame_size: int = 0

    def fill(self, out: Data, frame_size: int) -> bool:
        if self._frame_size and frame_size != self._frame_size:
            # Hope this never happens
            print("framesize change", self._frame_size, frame_size)
        self._frame_size = frame_size
        success = self._fill(out)
        self._chunk_count += 1
        return success

    @abstractmethod
    def _fill(self, out: Data) -> bool:
        pass

    @property
    def frame_count(self) -> int:
        return self._frame_size * self._chunk_count

    @property
    def frame_size(self) -> int:
        return self._frame_size

    @cached_property
    def _playback(self) -> Playback:
        return Playback(config=self.config, fill=self.fill)

    def run(self) -> None:
        self._playback.run()

    def stop(self) -> None:
        self._playback.stop()
