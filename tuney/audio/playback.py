from __future__ import annotations

import dataclasses as dc
import threading
from functools import cached_property
from typing import Protocol, TypeAlias

from sounddevice import CallbackStop, OutputStream

from .device_config import DeviceConfig
from .runnable import Runnable

import numpy as np

Data: TypeAlias = np.ndarray


class Filler(Protocol):
    def __call__(self, out: Data, frame_size: int) -> bool: ...


class Playback(Runnable):
    def __init__(self, config: DeviceConfig, fill: Filler) -> None:
        self.config = config
        self.fill = fill
        self._event = threading.Event()

    def callback(self, out: Data, frame_size: int, time: float, status: str) -> None:
        if status:
            print("Playback", status)  # TODO:

        if not self.fill(out, frame_size) or not self.is_running:
            self.stop()
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
