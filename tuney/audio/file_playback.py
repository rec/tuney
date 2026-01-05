from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from .playback import Playback
from .sample_data import Data, SampleData


@dc.dataclass
class FilePlayback:
    filename: str
    device: str | int = 0

    def run(self) -> None:
        self._playback.run()

    @cached_property
    def _data(self) -> SampleData:
        return SampleData.make(self.filename).cut_to(1.5)

    def _next_chunk(self, frames: int) -> Data:
        frame_count = self._playback.frame_count
        return self._data.data[frame_count : frame_count + frames]

    @cached_property
    def _playback(self) -> Playback:
        config = self._data.config(self.device)
        return Playback(config=config, next_chunk=self._next_chunk)


if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        print("open", a)
        FilePlayback(a).run()
