from __future__ import annotations

from functools import cached_property

from . import Data, DeviceConfig
from .player import Player
from .sample_data import SampleData


class FilePlayer(Player):
    def __init__(self, filename: str, device: str | int = 0) -> None:
        self.filename = filename
        self.device = device

    @cached_property
    def _data(self) -> SampleData:
        return SampleData.make(self.filename).cut_to(1.5)

    def _next_chunk(self, frames: int) -> Data:
        return self._data.data[self.frame_count : self.frame_count + frames]

    def _config(self) -> DeviceConfig:
        return self._data.config(self.device)


if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        print("open", a)
        FilePlayer(a).run()
