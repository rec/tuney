from __future__ import annotations

import dataclasses as dc
import time
from contextlib import suppress
from functools import cached_property
from typing import cast

import numpy as np

from ..runnable import start_thread
from ..scale.scale import NoteNumber, ScaleImpl
from ..types import Data, Number
from . import oscillator as osc
from .device_config import DeviceConfig
from .player import Player

INTENSITY = 0.1
FADE = 0  # 0x40000


@dc.dataclass(frozen=True)
class Sound:
    period: Number = 0x100
    intensity: Number = INTENSITY
    fade_in_samples: Number = 0x1000
    fade_out_samples: Number = 0x1000


@dc.dataclass
class OscillatorPlayer(Player):
    sound: Sound = Sound()
    oscillator_name: str = 'sawtooth'

    _stopping: bool = False

    #: Records the the frame we started to fade out.
    _fade_frame: Number | None = None

    @cached_property
    def oscillator(self) -> osc.Oscillator:
        return getattr(osc, self.oscillator_name)

    def stop(self) -> None:
        if self.sound.fade_out_samples > 0:
            self._stopping = True
        else:
            super().stop()

    def _fill(self, out: Data) -> bool:
        period = cast(float, self.sound.period)
        start = self.frame_count % period
        end = start + len(out)
        ratio = cast(float, self.oscillator.period) / period
        wave = np.linspace(start * ratio, end * ratio, len(out))
        wave = self.oscillator.function(wave, out=wave)

        intensity = self.sound.intensity
        with suppress(ValueError):
            # Scale up from [-1, 1] for int types only
            intensity *= np.iinfo(out.dtype).max
        wave *= intensity

        fade_in = cast(float, self.sound.fade_in_samples)
        if self.frame_count < fade_in and not self._stopping:
            _fade(wave, cast(float, self.frame_count) / fade_in, len(out) / fade_in)

        elif self._stopping:
            if self._fade_frame is None:
                # Account for the case when we fade out before we've faded in
                offset = max(0.0, fade_in - self.frame_count)
                self._fade_frame = self.frame_count - offset

            fade_out = cast(float, self.sound.fade_out_samples)
            elapsed = cast(float, self.frame_count - self._fade_frame)
            if (start := 1 - elapsed / fade_out) <= 0:
                super().stop()
                return False

            _fade(wave, start, -len(out) / fade_out)

        wave = wave.reshape((len(wave), 1))
        out[:] = np.asarray(wave, dtype=out.dtype)
        return True


@dc.dataclass(frozen=True)
class OscillatorController:
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


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _fade(wave: Data, start: float, length: float) -> None:
    wave *= np.linspace(_clamp(start), _clamp(start + length), len(wave))


def run_many_notes():
    oc = OscillatorController()
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
