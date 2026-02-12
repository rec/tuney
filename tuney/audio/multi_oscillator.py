from __future__ import annotations

import dataclasses as dc
import time
from functools import cached_property

from tuney.audio.device_config import DeviceConfig
from tuney.audio.oscillator_player import OscillatorPlayer, Sound
from tuney.runnable import start_thread
from tuney.scale.scale import ScaleImpl
from tuney.types import NoteNumber


@dc.dataclass(frozen=True)
class MultiOscillator:
    config: DeviceConfig = dc.field(default_factory=DeviceConfig)
    oscillator_name: str = 'sawtooth'
    scale: ScaleImpl = ScaleImpl()
    note_offset: NoteNumber = 0

    @cached_property
    def players(self) -> dict[int, OscillatorPlayer]:
        return {}

    def note(self, note_number: NoteNumber, is_press: bool) -> bool:
        return self.start(note_number) if is_press else self.stop(note_number)

    def start(self, note_number: NoteNumber) -> bool:
        if note_number in self.players:
            return False
        frequency = self.scale.tuning(note_number + self.note_offset)
        period = (self.config.samplerate or 48_000) / frequency
        sound = Sound(period)
        op = OscillatorPlayer(
            config=self.config, oscillator_name=self.oscillator_name, sound=sound
        )
        start_thread(op.run)
        self.players[note_number] = op
        return True

    def stop(self, note_number: NoteNumber) -> bool:
        if (op := self.players.pop(note_number, None)) is not None:
            op.stop()
        return bool(op)

    def stop_all(self) -> None:
        for player in self.players.values():
            player.stop()
        self.players.clear()
