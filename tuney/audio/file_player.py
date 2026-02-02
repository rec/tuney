from __future__ import annotations

from functools import cached_property

from .device_config import DeviceConfig
from .player import Player
from .sample_data import Data, SampleData


class FilePlayer(Player):
    def __init__(self, filename: str, device: str | int = 0) -> None:
        self.filename = filename
        self.device = device

    @cached_property
    def _data(self) -> SampleData:
        return SampleData.make(self.filename).cut_to(1.5)

    @cached_property
    def config(self) -> DeviceConfig:
        return self._data.config(self.device)

    def _fill(self, out: Data) -> bool:
        chunk = self._data.data[self.frame_count : self.frame_count + self.frame_size]
        out[: len(chunk)] = chunk
        success = len(chunk) == self.frame_size
        if not success:
            out[len(chunk) : self.frame_size] = 0
        return success


if __name__ == '__main__':
    import sys

    for a in sys.argv[1:]:
        print('open', a)
        FilePlayer(a).run()
