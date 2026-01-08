from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property

from .device_config import DeviceConfig
from .playback import Data, Playback


class Player(ABC):
    chunk_count: int = 0
    frame_size: int = 0

    config: DeviceConfig

    def fill(self, out: Data, frame_size: int) -> bool:
        if self.frame_size and frame_size != self.frame_size:
            # Hope this never happens
            print("framesize change", self.frame_size, frame_size)
        self.frame_size = frame_size
        success = self._fill(out)
        self.chunk_count += 1
        return success

    @abstractmethod
    def _fill(self, out: Data) -> bool:
        pass

    @property
    def frame_count(self) -> int:
        return self.frame_size * self.chunk_count

    @cached_property
    def _playback(self) -> Playback:
        return Playback(config=self.config, fill=self.fill)

    def run(self) -> None:
        self._playback.run()

    def stop(self) -> None:
        self._playback.stop()
