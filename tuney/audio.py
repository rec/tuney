from __future__ import annotations

import dataclasses as dc
import threading
from functools import cached_property
from typing import Protocol, TypeAlias
from queue import Queue

from sounddevice import CallbackStop, OutputStream
import soundfile
import numpy as np

Data: TypeAlias = np.ndarray


class DataChunker(Protocol):
    def __call__(self, frames: int) -> Data: ...


@dc.dataclass
class Playback:
    channels: int
    device: int | str
    next_chunk: DataChunker
    sample_rate: int

    _event: threading.Event = dc.field(default_factory=threading.Event)
    _running: bool = False

    def callback(self, out: Data, frames: int, time: float, status: str) -> None:
        if status:
            print("Playback", status)  # TODO:
        chunk = self.next_chunk(frames)
        out[: len(chunk)] = chunk
        if len(chunk) < frames:
            out[len(chunk) : frames] = 0
            self._running = False

        if not self._running:
            raise CallbackStop

    def run(self):
        self._running = True
        try:
            with self.stream:
                self._event.wait()
        finally:
            self.stop()

    def stop(self):
        self._running = False

    @cached_property
    def stream(self) -> OutputStream:
        return OutputStream(
            callback=self.callback,
            channels=self.channels,
            device=self.device,
            samplerate=self.sample_rate,
            finished_callback=self._event.set,
        )


@dc.dataclass
class SampleData:
    data: Data
    sample_rate: int

    @staticmethod
    def make(filename: str) -> SampleData:
        return SampleData(*soundfile.read(filename, always_2d=True))

    @cached_property
    def channels(self) -> int:
        return self.data.shape[1]


@dc.dataclass
class FilePlayback:
    filename: str
    device: str | int = 0

    chunk_count: int = 0
    frame_count: int = 0

    @cached_property
    def data(self) -> SampleData:
        return SampleData.make(self.filename)

    @cached_property
    def playback(self) -> Playback:
        return Playback(
            channels=self.data.channels,
            device=self.device,
            next_chunk=self.next_chunk,
            sample_rate=self.data.sample_rate,
        )

    def next_chunk(self, frames: int) -> Data:
        chunk = self.data.data[self.frame_count : self.frame_count + frames]
        self.frame_count += len(chunk)
        self.chunk_count += 1
        return chunk

    def run(self) -> None:
        self.playback.run()


@dc.dataclass
class SynthPlayback:
    _queue: Queue = dc.field(default_factory=Queue)


if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        print("open", a)
        FilePlayback(a).run()
