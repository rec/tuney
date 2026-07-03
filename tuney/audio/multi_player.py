from __future__ import annotations

from collections.abc import Callable
from functools import cached_property, partial
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from ..display import Display
from ..scale import NoteNumber
from ..scale.scale import Scale
from ..tyro_option import tyro_option
from .device import Device
from .engine import AudioEngine, Configure, StopAll, port_audio_error
from .mixer import Mixer, NotePress
from .oscillator import Oscillator
from .output_file import AudioFileWriter, render_file
from .voice import Voice


class MultiPlayer(BaseModel, frozen=True):
    device: Device = Field(default_factory=Device)
    oscillator: Oscillator = Oscillator()
    scale: Scale = Scale()

    # Audio output gain
    gain: Annotated[
        float,
        tyro_option(aliases=['-G']),
        Display(general=True, beginner=True, step=0.01, dial=True),
    ] = 1.0

    # Offset added to generated note numbers before tuning
    note_offset: Annotated[
        NoteNumber,
        tyro_option(name='audio-note-offset', aliases=['-n']),
        Display(general=True, beginner=True),
    ] = 44

    # Divisor applied to mixed voices to provide polyphonic headroom
    polyphonic_headroom: Annotated[float, tyro_option(), Display(row=0, order=1)] = (
        Field(4, gt=0)
    )

    # Maximum number of notes that can play simultaneously
    max_polyphony: Annotated[int, tyro_option(), Display(row=0, order=2)] = Field(
        32, gt=0
    )

    # Minimum duration of each synthesized note, in seconds
    minimum_note_time: Annotated[
        float, tyro_option(aliases=['-N']), Display(beginner=True, row=0)
    ] = Field(0.5, ge=0)

    @cached_property
    def pressed_notes(self) -> list[NoteNumber]:
        return []

    @cached_property
    def engine(self) -> AudioEngine:
        engine = AudioEngine(
            mixer=Mixer(
                sound=self.sound,
                polyphonic_headroom=self.polyphonic_headroom,
                max_polyphony=self.max_polyphony,
            ),
            device=self.device,
        )
        self.device.set_change_callback(self.reconfigure_device)
        return engine

    def reconfigure_device(self) -> None:
        self.pressed_notes.clear()
        try:
            self.engine.reconfigure()
        except port_audio_error():
            pass

    def sound(self, note_number: int, sample_rate: float | None = None) -> Voice:
        scaled_note_number = note_number + self.note_offset
        frequency = self.scale.frequency(scaled_note_number)
        return Voice(
            frequency=frequency,
            gain=self.gain * self.oscillator.gain(scaled_note_number),
            minimum_note_time=self.minimum_note_time,
            oscillator=self.oscillator,
            sample_rate=sample_rate or self.device.samplerate or 48_000,
        )

    @property
    def sample_rate(self) -> int:
        return self.device.samplerate or 48_000

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
            sound=partial(self.sound, sample_rate=self.sample_rate),
            channels=self.channels,
            polyphonic_headroom=self.polyphonic_headroom,
            max_polyphony=self.max_polyphony,
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
            path,
            int(stream.samplerate),
            int(stream.channels),
            comment,
            append,
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
            or len(self.pressed_notes) >= self.max_polyphony
        ):
            return False
        self.pressed_notes.append(note_number)
        try:
            sound = partial(self.sound, sample_rate=self.engine.stream.samplerate)
            self.engine.submit(
                Configure(
                    sound=sound,
                    polyphonic_headroom=self.polyphonic_headroom,
                    max_polyphony=self.max_polyphony,
                )
            )
            self.engine.submit(NotePress(note_number))
            self.engine.start()
        except port_audio_error():
            self.pressed_notes.remove(note_number)
            self.engine.close()
            return False
        return True

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
