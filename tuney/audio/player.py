from __future__ import annotations

from collections.abc import Callable
from functools import cached_property, partial
from pathlib import Path

from pydantic import BaseModel, Field

from ..app.platform_info import instrument, trace
from ..scale import NoteNumber
from ..scale.scale import Scale
from ..scale.tuning import Tuning
from .device import Device
from .engine import AudioEngine, Configure, PlaySpeech, StopAll
from .mixer import Mixer, NotePress
from .output_file import AudioFileWriter, render_file
from .sound import Sound
from .speech import SpeechPhrase, SpeechPlayback, SpeechRequest, render_speech
from .voice import Voice


class PreparedSpeech(BaseModel):
    request: SpeechRequest | None = None
    playback: SpeechPlayback | None = None

    def prepare(self, request: SpeechRequest) -> None:
        self.request = request
        self.playback = render_speech(request)

    def take(self, request: SpeechRequest) -> SpeechPlayback | None:
        if self.request != request:
            return None
        playback, self.playback = self.playback, None
        return playback


class Player(BaseModel, frozen=True):
    device: Device = Field(default_factory=Device)
    sound: Sound = Field(default_factory=Sound)
    scale: Scale = Field(default_factory=Scale)
    tuning: Tuning = Field(default_factory=Tuning)
    buffer_size: int = 32
    increase_buffer_size: Callable[[], int] | None = None

    @cached_property
    def pressed_notes(self) -> list[NoteNumber]:
        return []

    @cached_property
    def engine(self) -> AudioEngine:
        mixer = Mixer(
            voice_maker=self.voice_maker,
            polyphony=self.sound.polyphony,
            synchronize_oscillators=self.sound.synchronize_oscillators,
        )
        engine = AudioEngine(
            mixer=mixer,
            master_gain=self.output_gain,
            buffer_size=self.buffer_size,
            increase_buffer_size=self.increase_buffer_size,
            device=(
                self.device.model_copy(update={'channels': self.channels})
                if self.sound.binaural.enable
                else self.device
            ),
        )
        self.device.set_change_callback(self.reconfigure_device)
        return engine

    def set_master_gain(self, master_gain: float) -> None:
        self.sound.master_gain = master_gain
        if 'engine' in self.__dict__:
            self.engine.master_gain = self.output_gain

    def sync_engine_device(self) -> bool:
        if 'engine' not in self.__dict__:
            return False
        device = (
            self.device.model_copy(update={'channels': self.channels})
            if self.sound.binaural.enable
            else self.device
        )
        if self.engine.device != device:
            self.engine.device = device
            self.engine.master_gain = self.output_gain
            self.engine.reconfigure()
            return True
        self.engine.master_gain = self.output_gain
        return False

    def reconfigure_device(self) -> None:
        instrument('player reconfigure device')
        self.pressed_notes.clear()
        synced = self.sync_engine_device()
        try:
            if not synced:
                self.engine.reconfigure()
        except Exception as e:
            if e.__class__.__name__ != 'PortAudioError':
                raise

    def voice_maker(
        self,
        note_number: int,
        sample_rate: int | None = None,
    ) -> Voice:
        scaled_note_number = note_number + self.sound.note_offset
        frequency = self.scale.frequency(self.tuning, scaled_note_number)
        return Voice(
            frequency=frequency,
            gain=self.sound.note_gain(scaled_note_number),
            minimum_note_time=self.sound.minimum_note_time,
            oscillator=self.sound.oscillator,
            sample_rate=sample_rate or self.device.sample_rate or 48_000,
            binaural=self.sound.binaural,
        )

    @property
    def sample_rate(self) -> int:
        return self.device.sample_rate or 48_000

    @property
    def channels(self) -> int:
        if self.sound.binaural.enable:
            return 2
        return self.device.channels or 1

    @property
    def output_gain(self) -> float:
        return self.sound.master_gain

    def render_file(
        self,
        path: Path,
        events: list[tuple[int, NotePress]],
        comment: Callable[[], str] | None = None,
    ) -> None:
        mixer = Mixer(
            voice_maker=partial(self.voice_maker, sample_rate=self.sample_rate),
            channels=self.channels,
            polyphony=self.sound.polyphony,
            synchronize_oscillators=self.sound.synchronize_oscillators,
        )
        render_file(
            path,
            mixer,
            events,
            self.sample_rate,
            self.channels,
            comment,
            self.output_gain,
        )

    def start_recording(
        self,
        path: Path,
        comment: Callable[[], str] | None = None,
        append: bool = False,
    ) -> None:
        instrument('player start recording', path=path, append=append)
        stream = self.engine.stream
        self.engine.recorder = AudioFileWriter(
            path, int(stream.samplerate), stream.channels, comment, append
        )

    def stop_recording(self) -> None:
        instrument('player stop recording')
        recorder, self.engine.recorder = self.engine.recorder, None
        if recorder:
            recorder.close()

    def on_note(self, note_number: NoteNumber, is_press: bool) -> bool:
        trace('player note', note=note_number, is_press=is_press)
        return self.start(note_number) if is_press else self.stop(note_number)

    def start(self, note_number: NoteNumber) -> bool:
        trace('player start note', note=note_number)
        if note_number in self.pressed_notes:
            return False
        self.sync_engine_device()
        stolen_notes: list[NoteNumber] = []
        voice_count = 2 if self.sound.binaural.enable else 1
        while (
            self.pressed_notes
            and len(self.pressed_notes) * voice_count + voice_count
            > self.sound.polyphony.max_voices
        ):
            stolen_notes.append(self.pressed_notes.pop(0))
        self.pressed_notes.append(note_number)
        try:
            voice_maker = partial(
                self.voice_maker,
                sample_rate=int(self.engine.stream.samplerate),
            )
            self.engine.submit(
                Configure(
                    voice_maker=voice_maker,
                    polyphony=self.sound.polyphony,
                    synchronize_oscillators=self.sound.synchronize_oscillators,
                )
            )
            for stolen_note in stolen_notes:
                self.engine.submit(NotePress(stolen_note, False))
            self.engine.submit(NotePress(note_number))
            self.engine.start()
            return True
        except Exception as e:
            if e.__class__.__name__ != 'PortAudioError':
                raise
            instrument(
                'player start note portaudio error',
                note=note_number,
                error=str(e),
            )
            self.pressed_notes.remove(note_number)
            for stolen_note in reversed(stolen_notes):
                self.pressed_notes.insert(0, stolen_note)
            self.engine.close()
            return False

    def stop(self, note_number: NoteNumber) -> bool:
        trace('player stop note', note=note_number)
        if note_number not in self.pressed_notes:
            return False
        self.pressed_notes.remove(note_number)
        self.engine.submit(NotePress(note_number, False))
        return True

    def stop_all(self) -> None:
        instrument('player stop all')
        self.pressed_notes.clear()
        if 'engine' in self.__dict__:
            self.engine.submit(StopAll())

    @cached_property
    def prepared_speech(self) -> PreparedSpeech:
        return PreparedSpeech()

    def prepare_speech(
        self, phrases: list[SpeechPhrase], level: float, speed: float, voice: str | None
    ) -> None:
        request = self.speech_request(phrases, level, speed, voice)
        instrument(
            'player prepare speech', phrases=len(phrases), level=level, speed=speed
        )
        self.prepared_speech.prepare(request)

    def start_speech(
        self, phrases: list[SpeechPhrase], level: float, speed: float, voice: str | None
    ) -> None:
        instrument(
            'player start speech', phrases=len(phrases), level=level, speed=speed
        )
        request = self.speech_request(phrases, level, speed, voice)
        speech = self.prepared_speech.take(request) or render_speech(request)
        if speech is not None:
            self.engine.submit(PlaySpeech(speech=speech))
            self.engine.start()

    def speech_request(
        self, phrases: list[SpeechPhrase], level: float, speed: float, voice: str | None
    ) -> SpeechRequest:
        return SpeechRequest(
            phrases=phrases,
            sample_rate=int(self.engine.stream.samplerate),
            level=level,
            speed=speed,
            voice=voice,
        )

    def close(self) -> None:
        instrument('player close')
        self.pressed_notes.clear()
        if 'engine' in self.__dict__:
            self.engine.close()

    def wait(self, timeout: float | None = None) -> None:
        instrument('player wait', timeout=timeout)
        if 'engine' in self.__dict__:
            self.engine.wait(timeout)
