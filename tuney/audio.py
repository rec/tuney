from __future__ import annotations

import dataclasses as dc
import threading
from functools import cached_property
from typing import TypeAlias

import sounddevice as sd
import soundfile as sf
import numpy as np
from abc import abstractmethod

Data: TypeAlias = np.ndarray


@dc.dataclass(frozen=True)
class SampleData:
    data: Data
    sample_rate: int

    @cached_property
    def channels(self) -> int:
        return self.data.shape[1]

    @staticmethod
    def from_file(filename: str) -> SampleData:
        return SampleData(*sf.read(filename, always_2d=True))

    def stream(self, **kwargs) -> sd.OutputStream:
        return sd.OutputStream(
            channels=self.channels,
            samplerate=self.sample_rate,
            **kwargs,
        )


@dc.dataclass
class PlaybackBase:
    data: SampleData
    device: int | str = 0

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
            raise sd.CallbackStop()

    def run(self):
        self._running = True
        try:
            with self.stream:
                self._event.wait()
        finally:
            self._running = False

    @cached_property
    def stream(self) -> sd.OutputStream:
        return self.data.stream(
            callback=self.callback,
            device=self.device,
            finished_callback=self._event.set,
        )


class DataPlayback(PlaybackBase):
    def next_chunk(self, frames: int) -> Data:
        return self.data.data[self._current_frame : self._current_frame + frames]

    @staticmethod
    def from_file(filename: str, device: int | str = 0) -> DataPlayback:
        return DataPlayback(SampleData.from_file(filename), device)


if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        print("open", a)
        DataPlayback.from_file(a).run()
