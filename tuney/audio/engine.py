from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from queue import Empty, SimpleQueue
from threading import Event
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ..types import NoteNumber
from .device import Device
from .diagnostics import AudioDiagnostics
from .mixer import Mixer, NotePress
from .output_file import AudioFileWriter
from .voice import Voice

if TYPE_CHECKING:
    from sounddevice import PortAudioError


class Stream(Protocol):
    active: bool
    samplerate: float
    channels: int

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


OutputStream: Callable[..., Stream] | None = None


def port_audio_error() -> type[PortAudioError]:
    from sounddevice import PortAudioError

    return PortAudioError


class Configure(BaseModel, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sound: Callable[[NoteNumber], Voice]
    polyphonic_headroom: float
    max_polyphony: int


class StopAll(BaseModel, frozen=True):
    pass


class AudioEngine(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mixer: Mixer
    device: Device = Field(default_factory=Device)
    diagnostics: AudioDiagnostics = Field(default_factory=AudioDiagnostics)
    recorder: AudioFileWriter | None = Field(default=None, exclude=True)
    stop_when_silent: bool = False

    @cached_property
    def commands(self) -> SimpleQueue[NotePress | Configure | StopAll]:
        return SimpleQueue()

    @cached_property
    def playback_complete(self) -> Event:
        return Event()

    @cached_property
    def stream(self) -> Stream:
        global OutputStream
        if OutputStream is None:
            from sounddevice import OutputStream as OutputStream_

            OutputStream = OutputStream_

        try:
            return OutputStream(callback=self.callback, **self.device.model_dump())
        except port_audio_error() as error:
            self.diagnostics.record_stream_error(str(error))
            raise

    def submit(self, command: NotePress | Configure | StopAll) -> None:
        self.commands.put(command)

    def start(self) -> None:
        self.playback_complete.clear()
        if 'stream' in self.__dict__ and self.stream.active:
            return
        try:
            self.stream.start()
        except port_audio_error() as error:
            if stream := self.__dict__.pop('stream', None):
                self.diagnostics.record_stream_error(str(error))
                stream.close()
            raise

    def close(self) -> None:
        if stream := self.__dict__.pop('stream', None):
            stream.stop()
            stream.close()
        self.__dict__.pop('commands', None)
        self.mixer.pressed_notes.clear()
        self.mixer.voices.clear()
        self.stop_when_silent = False

    def reconfigure(self) -> None:
        restart = 'stream' in self.__dict__ and self.stream.active
        self.close()
        if restart:
            self.start()

    def wait(self) -> None:
        stream = self.__dict__.get('stream')
        if stream is not None:
            self.playback_complete.wait()
            stream.stop()

    def callback(
        self, out: np.ndarray, frame_size: int, time: Any, status: Any
    ) -> None:
        if status:
            self.diagnostics.record_callback_status(str(status))

        try:
            self._drain_commands()
            out[:] = self.mixer.render(frame_size, out.dtype, out.shape[1])
            if self.recorder:
                self.recorder.write(out)
        except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
            from sounddevice import CallbackAbort

            self.diagnostics.record_callback_error(str(error))
            self.playback_complete.set()
            raise CallbackAbort from error
        if self.stop_when_silent and not self.mixer.voices:
            self.playback_complete.set()

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
