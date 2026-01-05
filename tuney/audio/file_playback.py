from __future__ import annotations

import dataclasses as dc
from functools import cached_property


from .playback import Playback
from .sample_data import Data, SampleData


@dc.dataclass
class FilePlayback:
    filename: str
    device: str | int = 0

    chunk_count: int = 0
    frame_count: int = 0

    def run(self) -> None:
        self._playback.run()

    @cached_property
    def _data(self) -> SampleData:
        return SampleData.make(self.filename).cut_to(1.5)

    def _next_chunk(self, frames: int) -> Data:
        chunk = self._data.data[self.frame_count : self.frame_count + frames]
        self.frame_count += len(chunk)
        self.chunk_count += 1
        return chunk

    @cached_property
    def _playback(self) -> Playback:
        return Playback(
            channels=self._data.channels,
            device=self.device,
            next_chunk=self._next_chunk,
            sample_rate=self._data.sample_rate,
        )


if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        print("open", a)
        FilePlayback(a).run()
