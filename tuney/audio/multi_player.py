from __future__ import annotations

from functools import cached_property

from pydantic import BaseModel

from ..scale.scale import Scale
from ..types import NoteNumber
from .device import Device
from .engine import AudioEngine, Configure, StopAll
from .mixer import Mixer, NotePress
from .oscillator import Oscillator
from .voice import Voice


class MultiPlayer(BaseModel, frozen=True):
    device: Device = Device()
    oscillator: Oscillator = Oscillator()
    scale: Scale = Scale()
    gain: float = 1.0
    note_offset: NoteNumber = 32

    @cached_property
    def pressed_notes(self) -> list[NoteNumber]:
        return []

    @cached_property
    def engine(self) -> AudioEngine:
        return AudioEngine(mixer=Mixer(sound=self.sound), device=self.device)

    def sound(self, note_number: int) -> Voice:
        frequency = self.scale.tuning(note_number + self.note_offset)
        return Voice(
            frequency=frequency,
            gain=self.gain,
            oscillator=self.oscillator,
            sample_rate=self.device.samplerate or 48_000,
        )

    def on_note(self, note_number: NoteNumber, is_press: bool) -> bool:
        return self.start(note_number) if is_press else self.stop(note_number)

    def start(self, note_number: NoteNumber) -> bool:
        if note_number in self.pressed_notes:
            return False
        self.pressed_notes.append(note_number)
        self.engine.submit(Configure(sound=self.sound))
        self.engine.submit(NotePress(note_number=note_number, is_press=True))
        self.engine.start()
        return True

    def stop(self, note_number: NoteNumber) -> bool:
        if note_number not in self.pressed_notes:
            return False
        self.pressed_notes.remove(note_number)
        self.engine.submit(NotePress(note_number=note_number, is_press=False))
        return True

    def stop_all(self) -> None:
        self.pressed_notes.clear()
        self.engine.submit(StopAll())

    def close(self) -> None:
        self.pressed_notes.clear()
        if 'engine' in self.__dict__:
            self.engine.close()
