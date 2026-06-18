from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from queue import Empty, SimpleQueue
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sounddevice import CallbackStop, OutputStream, PortAudioError

from ..types import NoteNumber
from .device import Device
from .diagnostics import AudioDiagnostics
from .mixer import Mixer, NotePress
from .voice import Voice


class Configure(BaseModel, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sound: Callable[[NoteNumber], Voice]
    polyphonic_headroom: float
    max_polyphony: int


class StopAll(BaseModel, frozen=True):
    pass


class AudioEngine(BaseModel):
    mixer: Mixer
    device: Device = Device()
    diagnostics: AudioDiagnostics = Field(default_factory=AudioDiagnostics)
    stop_when_silent: bool = False

    @cached_property
    def commands(self) -> SimpleQueue[NotePress | Configure | StopAll]:
        return SimpleQueue()

    @cached_property
    def stream(self) -> OutputStream:
        return OutputStream(callback=self.callback, **self.device.model_dump())

    def submit(self, command: NotePress | Configure | StopAll) -> None:
        self.commands.put(command)

    def start(self) -> None:
        if 'stream' in self.__dict__ and self.stream.active:
            return
        try:
            self.stream.start()
        except PortAudioError as error:
            self.diagnostics.record_stream_error(str(error))
            raise

    def close(self) -> None:
        if 'stream' in self.__dict__:
            self.stream.stop()
            self.stream.close()
        self.mixer.pressed_notes.clear()
        self.mixer.voices.clear()

    def callback(
        self, out: np.ndarray, frame_size: int, time: Any, status: Any
    ) -> None:
        if status:
            self.diagnostics.record_callback_status(str(status))

        self._drain_commands()
        out[:] = self.mixer.render(frame_size, out.dtype, out.shape[1])
        if self.stop_when_silent and not self.mixer.voices:
            raise CallbackStop

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except Empty:
                return

            if isinstance(command, NotePress):
                self.stop_when_silent = False
                self.mixer.apply(command)
            elif isinstance(command, Configure):
                self.mixer.sound = command.sound
                self.mixer.polyphonic_headroom = command.polyphonic_headroom
                self.mixer.max_polyphony = command.max_polyphony
            else:
                self.stop_when_silent = True
                self.mixer.stop_all()
