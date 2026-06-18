from __future__ import annotations

from functools import cached_property

from pydantic import BaseModel

from ..scale.scale import Scale
from ..types import NoteNumber
from . import concurrent, oscillator_player
from .device import Device
from .oscillator import Oscillator
from .voice import Voice


class MultiPlayer(BaseModel, frozen=True):
    device: Device = Device()
    oscillator: Oscillator = Oscillator()
    scale: Scale = Scale()
    gain: float = 1.0
    note_offset: NoteNumber = 32

    @cached_property
    def stoppable_futures(self) -> dict[int, concurrent.StoppableFuture]:
        return {}

    @cached_property
    def runner(self) -> concurrent.Runner:
        return concurrent.Runner(function=oscillator_player.run)

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
        if success := note_number not in self.stoppable_futures:
            self.stoppable_futures[note_number] = self.runner(
                device=self.device,
                sound=self.sound(note_number),
            )
        return success

    def stop(self, note_number: NoteNumber) -> bool:
        if sf := self.stoppable_futures.pop(note_number, None):
            sf.stop()
        return bool(sf)

    def stop_all(self) -> None:
        sfs = list(self.stoppable_futures.values())
        self.stoppable_futures.clear()
        for sf in sfs:
            sf.stop()
