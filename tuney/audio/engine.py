from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from queue import Empty, SimpleQueue
from threading import Event
from typing import Any, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ..scale import NoteNumber
from .device import Device, output_device
from .diagnostics import AudioDiagnostics
from .mixer import Mixer, NotePress
from .output_file import AudioFileWriter
from .polyphony import Polyphony
from .voice import Voice


@runtime_checkable
class Stream(Protocol):
    active: bool
    samplerate: float | int
    channels: int

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


class Configure(BaseModel, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    voice_maker: Callable[[NoteNumber], Voice]
    polyphony: Polyphony


class StopAll:
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
        import sounddevice as sd

        kwargs = self.device.model_dump()
        kwargs['samplerate'] = kwargs.pop('sample_rate')
        kwargs['device'] = output_device(kwargs['device'])
        try:
            return sd.OutputStream(callback=self.callback, **kwargs)
        except sd.PortAudioError as error:
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
        except Exception as error:
            if error.__class__.__name__ == 'PortAudioError':
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
        if (stream := self.__dict__.get('stream')) is not None:
            if stream.active:
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
                self.mixer.voice_maker = command.voice_maker
                self.mixer.polyphony = command.polyphony
            else:
                self.stop_when_silent = True
                self.mixer.stop_all()
