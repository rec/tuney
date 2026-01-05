from __future__ import annotations

import dataclasses as dc
import threading
from functools import cached_property
from typing import Protocol

from sounddevice import CallbackStop, OutputStream

from . import Data, DeviceConfig
from .runnable import Runnable


class DataChunker(Protocol):
    def __call__(self, frames: int) -> Data: ...


class Playback(Runnable):
    def __init__(self, config: DeviceConfig, next_chunk: DataChunker) -> None:
        self.config = config
        self.next_chunk = next_chunk
        self._event = threading.Event()

    def callback(self, out: Data, frames: int, time: float, status: str) -> None:
        if status:
            print("Playback", status)  # TODO:
        chunk = self.next_chunk(frames)
        out[: len(chunk)] = chunk
        if len(chunk) < frames:
            out[len(chunk) : frames] = 0
            self.stop()

        if not self.is_running:
            raise CallbackStop

    def _run(self):
        with self.stream:
            self._event.wait()

    @cached_property
    def stream(self) -> OutputStream:
        kwargs = dc.asdict(self.config)
        return OutputStream(
            callback=self.callback,
            finished_callback=self._event.set,
            samplerate=kwargs.pop("sample_rate"),
            **kwargs,
        )
