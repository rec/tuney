from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property


from . import Data, DeviceConfig
from .playback import Playback


class Player(ABC):
    config: DeviceConfig
    chunk_count: int = 0
    frame_count: int = 0

    @cached_property
    def config(self) -> DeviceConfig:
        return self._config()

    def next_chunk(self, frames: int) -> Data:
        chunk = self._next_chunk(frames)
        self.frame_count += len(chunk)
        self.chunk_count += 1
        return chunk

    @abstractmethod
    def _config(self) -> DeviceConfig: ...

    @abstractmethod
    def _next_chunk(self, frames: int) -> Data: ...

    @cached_property
    def _playback(self) -> Playback:
        return Playback(config=self.config, next_chunk=self.next_chunk)

    def run(self) -> None:
        self._playback.run()
