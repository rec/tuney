from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from queue import Empty, SimpleQueue
from threading import Event
from typing import Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from ufor.number import NoteNumber

from ..app.platform_info import instrument, trace
from .device import Device, output_device
from .diagnostics import AudioDiagnostics
from .mixer import Mixer, NotePress
from .polyphony import Polyphony
from .recording import Recording
from .speech import SpeechPlayback
from .voice import Voice, VoiceState


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


class PreparedNote(BaseModel, frozen=True):
    note: NotePress
    voice: VoiceState | None = None


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
    recorder: Recording | None = Field(default=None, exclude=True)
    speech: SpeechPlayback | None = Field(default=None, exclude=True)
    stop_when_silent: bool = False

    @cached_property
    def commands(self) -> SimpleQueue[PreparedNote | Configure | PlaySpeech | StopAll]:
        return SimpleQueue()

    @cached_property
    def notifications(self) -> SimpleQueue[tuple[bool, str]]:
        return SimpleQueue()

    @cached_property
    def voice_maker(self) -> Callable[[NoteNumber], Voice]:
        return self.mixer.voice_maker

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
            instrument(
                'audio stream create',
                requested_device=self.device.device,
                resolved_device=kwargs['device'],
                sample_rate=kwargs['samplerate'],
                channels=kwargs['channels'],
                dtype=_display_value(kwargs['dtype']),
                blocksize=kwargs['blocksize'],
                clip_off=kwargs['clip_off'],
                dither_off=kwargs['dither_off'],
                never_drop_input=kwargs['never_drop_input'],
                prime_output_buffers_using_stream_callback=kwargs[
                    'prime_output_buffers_using_stream_callback'
                ],
                sounddevice_defaults=_sounddevice_defaults(sd),
                resolved_device_info=_sounddevice_device_info(sd, kwargs['device']),
            )
            stream = sd.OutputStream(callback=self.callback, **kwargs)
            instrument('audio stream created', **_stream_info(stream))
            return stream
        except sd.PortAudioError as error:
            instrument('audio stream create error', error=str(error))
            self.diagnostics.record_stream_error(str(error))
            raise

    def submit(self, command: NotePress | Configure | PlaySpeech | StopAll) -> None:
        trace('audio command submit', command=type(command).__name__)
        if isinstance(command, Configure):
            self.__dict__['voice_maker'] = command.voice_maker
        if isinstance(command, NotePress):
            voice = (
                VoiceState(voice=self.voice_maker(command.note_number))
                if command.is_press
                else None
            )
            self.commands.put(PreparedNote(note=command, voice=voice))
        else:
            self.commands.put(command)

    def process_notifications(self) -> None:
        if (recorder := self.recorder) is not None:
            if recorder.error is not None and not recorder.error_reported:
                recorder.error_reported = True
                self.diagnostics.record_callback_error(
                    f'Recording failed: {recorder.error}'
                )
        while True:
            try:
                failed, message = self.notifications.get_nowait()
            except Empty:
                return
            if failed:
                instrument('audio callback error', error=message)
                self.diagnostics.record_callback_error(message)
            else:
                if 'underflow' in message.lower():
                    if self.increase_buffer_size is not None:
                        self.buffer_size = self.increase_buffer_size()
                    message = f'{message}; buffer_size={self.buffer_size}'
                instrument('audio callback status', status=message)
                self.diagnostics.record_callback_status(message)

    def start(self) -> None:
        self.playback_complete.clear()
        if 'stream' in self.__dict__ and self.stream.active:
            return
        try:
            instrument('audio stream start', **_stream_info(self.stream))
            self.stream.start()
            instrument('audio stream started', **_stream_info(self.stream))
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
        self.process_notifications()
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

    def wait(self, timeout: float | None = None) -> None:
        if (stream := self.__dict__.get('stream')) is not None:
            if stream.active:
                instrument('audio stream wait', timeout=timeout)
                completed = self.playback_complete.wait(timeout)
                if not completed:
                    instrument('audio stream wait timeout')
                stream.stop()
                instrument('audio stream stopped after wait')
        self.process_notifications()

    def callback(
        self, out: np.ndarray, frame_size: int, time: object, status: object
    ) -> None:
        if status:
            self.notifications.put((False, str(status)))

        try:
            self._drain_commands()
            mixed = self.mixer.render(frame_size, float, out.shape[1])
            if self.speech is not None:
                mixed += self.speech.render(frame_size, float, out.shape[1])
                if self.speech.complete:
                    self.speech = None
            mixed *= self.master_gain
            out[:] = mixed.astype(out.dtype, copy=False)
            if (recorder := self.recorder) is not None:
                recorder.write(out)
        except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
            from sounddevice import CallbackAbort

            self.notifications.put((True, str(error)))
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

            if isinstance(command, PreparedNote):
                self.stop_when_silent = False
                self.mixer.apply(command.note, command.voice)
            elif isinstance(command, Configure):
                self.mixer.voice_maker = command.voice_maker
                self.mixer.polyphony = command.polyphony
                self.mixer.synchronize_oscillators = command.synchronize_oscillators
            elif isinstance(command, PlaySpeech):
                self.speech = command.speech
            else:
                self.stop_when_silent = True
                self.speech = None
                self.mixer.stop_all()


def _stream_info(stream: Stream) -> dict[str, object]:
    return {
        'active': stream.active,
        'samplerate': stream.samplerate,
        'channels': stream.channels,
        'blocksize': getattr(stream, 'blocksize', None),
        'latency': getattr(stream, 'latency', None),
        'dtype': _display_value(getattr(stream, 'dtype', None)),
        'device': getattr(stream, 'device', None),
        'closed': getattr(stream, 'closed', None),
    }


def _display_value(value: object) -> object:
    return str(value) if value is not None else None


def _sounddevice_defaults(sd: object) -> object:
    return getattr(sd, 'default', None)


def _sounddevice_device_info(sd: object, device: int | str | None) -> object:
    if device is None:
        return None
    if not callable(query_devices := getattr(sd, 'query_devices', None)):
        return None
    port_audio_error = getattr(sd, 'PortAudioError', None)
    errors = (OSError, RuntimeError, TypeError, ValueError)
    if isinstance(port_audio_error, type) and issubclass(
        port_audio_error, BaseException
    ):
        errors = (*errors, port_audio_error)
    try:
        return query_devices(device)
    except errors as error:
        return f'{type(error).__name__}: {error}'
