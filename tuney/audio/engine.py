from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from queue import Empty, SimpleQueue
from threading import Event
from typing import Any, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ..app.platform_info import instrument, trace
from ..scale import NoteNumber
from .device import Device, output_device
from .diagnostics import AudioDiagnostics
from .mixer import Mixer, NotePress
from .output_file import AudioFileWriter
from .polyphony import Polyphony
from .speech import SpeechPlayback
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
    synchronize_oscillators: bool = False


class StopAll:
    pass


class PlaySpeech(BaseModel, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    speech: SpeechPlayback


class AudioEngine(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mixer: Mixer
    master_gain: float = 1.0
    buffer_size: int = 32
    increase_buffer_size: Callable[[], int] | None = Field(default=None, exclude=True)
    device: Device = Field(default_factory=Device)
    diagnostics: AudioDiagnostics = Field(default_factory=AudioDiagnostics)
    recorder: AudioFileWriter | None = Field(default=None, exclude=True)
    speech: SpeechPlayback | None = Field(default=None, exclude=True)
    stop_when_silent: bool = False

    @cached_property
    def commands(self) -> SimpleQueue[NotePress | Configure | PlaySpeech | StopAll]:
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
        kwargs['blocksize'] = self.buffer_size
        try:
            instrument('audio stream create', kwargs=kwargs)
            return sd.OutputStream(callback=self.callback, **kwargs)
        except sd.PortAudioError as error:
            instrument('audio stream create error', error=str(error))
            self.diagnostics.record_stream_error(str(error))
            raise

    def submit(self, command: NotePress | Configure | PlaySpeech | StopAll) -> None:
        trace('audio command submit', command=type(command).__name__)
        self.commands.put(command)

    def start(self) -> None:
        self.playback_complete.clear()
        if 'stream' in self.__dict__ and self.stream.active:
            return
        try:
            instrument('audio stream start')
            self.stream.start()
            instrument('audio stream started')
        except Exception as error:
            if error.__class__.__name__ == 'PortAudioError':
                if stream := self.__dict__.pop('stream', None):
                    instrument('audio stream start error', error=str(error))
                    self.diagnostics.record_stream_error(str(error))
                    stream.close()
            raise

    def close(self) -> None:
        instrument('audio engine close')
        if stream := self.__dict__.pop('stream', None):
            stream.stop()
            stream.close()
        self.__dict__.pop('commands', None)
        self.mixer.pressed_notes.clear()
        self.mixer.voices.clear()
        self.stop_when_silent = False

    def reconfigure(self) -> None:
        restart = 'stream' in self.__dict__ and self.stream.active
        instrument('audio engine reconfigure', restart=restart)
        self.close()
        if restart:
            self.start()

    def wait(self) -> None:
        if (stream := self.__dict__.get('stream')) is not None:
            if stream.active:
                instrument('audio stream wait')
                self.playback_complete.wait()
                stream.stop()
                instrument('audio stream stopped after wait')

    def callback(
        self, out: np.ndarray, frame_size: int, time: Any, status: Any
    ) -> None:
        if status:
            status_text = str(status)
            if 'underflow' in status_text.lower():
                if self.increase_buffer_size is not None:
                    self.buffer_size = self.increase_buffer_size()
                status_text = f'{status_text}; buffer_size={self.buffer_size}'
            instrument('audio callback status', status=status_text)
            self.diagnostics.record_callback_status(status_text)

        try:
            self._drain_commands()
            out[:] = self.mixer.render(frame_size, out.dtype, out.shape[1])
            if self.speech is not None:
                out += self.speech.render(frame_size, out.dtype, out.shape[1])
                np.clip(out, -1, 1, out=out)
                if self.speech.complete:
                    self.speech = None
            out *= self.master_gain
            np.clip(out, -1, 1, out=out)
            if self.recorder:
                self.recorder.write(out)
        except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
            from sounddevice import CallbackAbort

            instrument('audio callback error', error=repr(error))
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
                trace(
                    'audio command apply',
                    command='NotePress',
                    note=command.note_number,
                    is_press=command.is_press,
                )
                self.stop_when_silent = False
                self.mixer.apply(command)
            elif isinstance(command, Configure):
                trace('audio command apply', command='Configure')
                self.mixer.voice_maker = command.voice_maker
                self.mixer.polyphony = command.polyphony
                self.mixer.synchronize_oscillators = command.synchronize_oscillators
            elif isinstance(command, PlaySpeech):
                trace('audio command apply', command='PlaySpeech')
                self.speech = command.speech
            else:
                trace('audio command apply', command='StopAll')
                self.stop_when_silent = True
                self.speech = None
                self.mixer.stop_all()
