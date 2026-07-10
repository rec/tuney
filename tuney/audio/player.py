from __future__ import annotations

from collections.abc import Callable
from functools import cached_property, partial
from pathlib import Path

from pydantic import BaseModel, Field

from ..scale import NoteNumber
from ..scale.scale import Scale
from ..scale.tuning import Tuning
from .device import Device
from .engine import AudioEngine, Configure, StopAll
from .mixer import Mixer, NotePress
from .output_file import AudioFileWriter, render_file
from .sound import Sound
from .voice import Voice


class Player(BaseModel, frozen=True):
    device: Device = Field(default_factory=Device)
    sound: Sound = Field(default_factory=Sound)
    scale: Scale = Field(default_factory=Scale)
    tuning: Tuning = Field(default_factory=Tuning)

    @cached_property
    def pressed_notes(self) -> list[NoteNumber]:
        return []

    @cached_property
    def engine(self) -> AudioEngine:
        mixer = Mixer(voice_maker=self.voice_maker, polyphony=self.sound.polyphony)
        engine = AudioEngine(mixer=mixer, device=self.device)
        self.device.set_change_callback(self.reconfigure_device)
        return engine

    def reconfigure_device(self) -> None:
        self.pressed_notes.clear()
        try:
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
        )

    @property
    def sample_rate(self) -> int:
        return self.device.sample_rate or 48_000

    @property
    def channels(self) -> int:
        return self.device.channels or 1

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
        )
        render_file(path, mixer, events, self.sample_rate, self.channels, comment)

    def start_recording(
        self,
        path: Path,
        comment: Callable[[], str] | None = None,
        append: bool = False,
    ) -> None:
        stream = self.engine.stream
        self.engine.recorder = AudioFileWriter(
            path, int(stream.samplerate), stream.channels, comment, append
        )

    def stop_recording(self) -> None:
        recorder, self.engine.recorder = self.engine.recorder, None
        if recorder:
            recorder.close()

    def on_note(self, note_number: NoteNumber, is_press: bool) -> bool:
        return self.start(note_number) if is_press else self.stop(note_number)

    def start(self, note_number: NoteNumber) -> bool:
        if (
            note_number in self.pressed_notes
            or len(self.pressed_notes) >= self.sound.polyphony.max_voices
        ):
            return False
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
                )
            )
            self.engine.submit(NotePress(note_number))
            self.engine.start()
            return True
        except Exception as e:
            if e.__class__.__name__ != 'PortAudioError':
                raise
            self.pressed_notes.remove(note_number)
            self.engine.close()
            return False

    def stop(self, note_number: NoteNumber) -> bool:
        if note_number not in self.pressed_notes:
            return False
        self.pressed_notes.remove(note_number)
        self.engine.submit(NotePress(note_number, False))
        return True

    def stop_all(self) -> None:
        self.pressed_notes.clear()
        self.engine.submit(StopAll())

    def close(self) -> None:
        self.pressed_notes.clear()
        if 'engine' in self.__dict__:
            self.engine.close()

    def wait(self) -> None:
        if 'engine' in self.__dict__:
            self.engine.wait()
