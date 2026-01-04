from __future__ import annotations

import dataclasses as dc
import threading
from abc import abstractmethod
from functools import cached_property
from typing import TypeAlias
from queue import Queue

from sounddevice import CallbackStop, OutputStream
import soundfile as sf
import numpy as np

Data: TypeAlias = np.ndarray


@dc.dataclass
class PlaybackBase:
    channels: int = 1
    device: int | str = 0
    sample_rate: int = 0

    _current_frame: int = 0
    _event: threading.Event = dc.field(default_factory=threading.Event)
    _running: bool = False

    @abstractmethod
    def next_chunk(self, frames: int) -> Data: ...

    def callback(self, out: Data, frames: int, time: float, status: str) -> None:
        if status:
            print("Playback", status)  # TODO:
        chunk = self.next_chunk(frames)
        self._current_frame += len(chunk)

        out[: len(chunk)] = chunk
        if len(chunk) < frames:
            out[len(chunk) : frames] = 0
            self._running = False

        if not self._running:
            raise CallbackStop()

    def run(self):
        self._running = True
        try:
            with self.stream:
                self._event.wait()
        finally:
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
class DataPlayback(PlaybackBase):
    data: Data = dc.field(default_factory=Data)

    def next_chunk(self, frames: int) -> Data:
        return self.data.data[self._current_frame : self._current_frame + frames]

    @staticmethod
    def from_file(filename: str, device: int | str = 0) -> DataPlayback:
        data, sample_rate = sf.read(filename, always_2d=True)
        return DataPlayback(
            channels=data.shape[1], data=data, device=device, sample_rate=sample_rate
        )


@dc.dataclass
class SynthPlayback(PlaybackBase):
    _queue: Queue = dc.field(default_factory=Queue)
    # @cached_property


if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        print("open", a)
        DataPlayback.from_file(a).run()
