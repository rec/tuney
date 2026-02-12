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


def run_many_notes():
    oc = MultiOscillator()
    DT = 0.2
    twelve_tet = ScaleImpl()

    stack = []
    o1 = 'C4', 'E4', 'D5', 'Eb3', 'G3', 'C3', 'E3', 'D4', 'Eb2', 'G2'
    o2 = 'C2', 'E2', 'D3', 'Eb1', 'G1', 'C1', 'E1', 'D2', 'Eb0', 'G0'

    for name in (o1 + o2)[0]:
        stack.append(note := twelve_tet.to_number(name))
        if not oc.start(note):
            print('oops', name)
        time.sleep(DT)

    while stack:
        if not oc.stop(note := stack.pop()):
            print('oops off', note)
        time.sleep(DT / 2)


if __name__ == '__main__':
    run_many_notes()
