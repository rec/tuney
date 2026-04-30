from __future__ import annotations

from functools import cached_property

from pydantic import BaseModel

from ..scale.scale import ScaleImpl
from ..types import NoteNumber
from . import concurrent
from .device import Device
from .oscillator_player import Sound, make_and_run, make_and_start


class MultiPlayer(BaseModel, frozen=True):
    device: Device = Device()
    oscillator_name: str = 'sawtooth'
    scale: ScaleImpl = ScaleImpl()
    gain: float = 1.0
    note_offset: NoteNumber = 0
    use_multiprocessing: bool = False

    @cached_property
    def stoppable_futures(self) -> dict[int, concurrent.StoppableFuture]:
        return {}

    @cached_property
    def runner(self) -> concurrent.Runner:
        return concurrent.Runner(make_and_run, self.use_multiprocessing)

    def note(self, note_number: NoteNumber, is_press: bool) -> bool:
        return self.start(note_number) if is_press else self.stop(note_number)

    def start(self, note_number: NoteNumber) -> bool:
        if note_number in self.stoppable_futures:
            return False
        frequency = self.scale.tuning(note_number + self.note_offset)
        period = (self.device.samplerate or 48_000) / frequency
        sound = Sound(period=period, gain=self.gain)
        assert isinstance(make_and_start, concurrent.StoppableFunction)
        self.stoppable_futures[note_number] = self.runner(
            device=self.device, oscillator_name=self.oscillator_name, sound=sound
        )
        return True

    def stop(self, note_number: NoteNumber) -> bool:
        if (sf := self.stoppable_futures.pop(note_number, None)) is None:
            return False
        sf.stop()
        return True

    def stop_all(self) -> None:
        sfs = list(self.stoppable_futures.values())
        self.stoppable_futures.clear()
        for sf in sfs:
            sf.stop()
