from __future__ import annotations

import dataclasses as dc
import threading
from functools import cached_property
from typing import Protocol, TypeAlias

from sounddevice import CallbackStop, OutputStream
import numpy as np

from . import DeviceConfig

Data: TypeAlias = np.ndarray


class DataChunker(Protocol):
    def __call__(self, frames: int) -> Data: ...


@dc.dataclass
class Playback:
    config: DeviceConfig
    next_chunk: DataChunker

    _event: threading.Event = dc.field(default_factory=threading.Event)
    _running: bool = False

    def callback(self, out: Data, frames: int, time: float, status: str) -> None:
        if status:
            print("Playback", status)  # TODO:
        chunk = self.next_chunk(frames)
        out[: len(chunk)] = chunk
        if len(chunk) < frames:
            out[len(chunk) : frames] = 0
            self.stop()

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
        kwargs = dc.asdict(self.config)
        return OutputStream(
            callback=self.callback,
            finished_callback=self._event.set,
            samplerate=kwargs.pop("sample_rate"),
            **kwargs,
        )
