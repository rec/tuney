from __future__ import annotations

import dataclasses as dc
from functools import cached_property

from ..runnable import start_thread
from ..scale.scale import ScaleImpl
from ..types import NoteNumber
from . import concurrent
from .device_config import DeviceConfig
from .oscillator_player import make_and_start, OscillatorPlayer, Sound


@dc.dataclass(frozen=True)
class MultiOscillator:
    config: DeviceConfig = DeviceConfig()
    oscillator_name: str = 'sawtooth'
    scale: ScaleImpl = ScaleImpl()
    gain: float = 1.0
    note_offset: NoteNumber = 0
    use_multiprocessing: bool = False

    @cached_property
    def stoppables(self) -> dict[int, concurrent.Stoppable]:
        return {}

    def note(self, note_number: NoteNumber, is_press: bool) -> bool:
        return self.start(note_number) if is_press else self.stop(note_number)

    def start(self, note_number: NoteNumber) -> bool:
        if note_number in self.stoppables:
            return False
        frequency = self.scale.tuning(note_number + self.note_offset)
        period = (self.config.samplerate or 48_000) / frequency
        sound = Sound(period, gain=self.gain)
        op = OscillatorPlayer(
            config=self.config, oscillator_name=self.oscillator_name, sound=sound
        )
        start_thread(op.run)
        self.stoppables[note_number] = op
        return True

    def stop(self, note_number: NoteNumber) -> bool:
        if (stoppable := self.stoppables.pop(note_number, None)) is None:
            return False
        stoppable.stop()
        return True

    def stop_all(self) -> None:
        for stoppable in self.stoppables.values():
            stoppable.stop()
        self.stoppables.clear()
