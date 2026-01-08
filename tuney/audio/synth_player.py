from __future__ import annotations

import dataclasses as dc
import time
from contextlib import suppress
from threading import Thread
from typing import Any, Callable, TypeAlias

import numpy as np

from .device_config import DeviceConfig
from .playback import Data
from .player import Player

Number: TypeAlias = int | float
Function: TypeAlias = Callable[..., Any]

INTENSITY = 0.1


@dc.dataclass(frozen=True)
class Sound:
    period: Number
    intensity: Number = INTENSITY


@dc.dataclass(frozen=True)
class Oscillator:
    function: Function = np.sin
    period: Number = 2 * np.pi


@dc.dataclass
class OscillatorPlayer(Player):
    config: DeviceConfig  # pyrefly: ignore[bad-override]
    oscillator: Oscillator
    sound: Sound

    def _fill(self, out: Data) -> bool:
        start = self.frame_count % self.sound.period
        end = start + len(out)
        ratio = self.oscillator.period / self.sound.period
        wave = np.linspace(start * ratio, end * ratio, len(out))
        wave = self.oscillator.function(wave, out=wave)

        intensity = self.sound.intensity
        with suppress(ValueError):
            # Scale up from [-1, 1] for int types only
            intensity *= np.iinfo(out.dtype).max
        wave *= intensity

        wave = wave.reshape((len(wave), 1))
        out[:] = np.asarray(wave, dtype=out.dtype)
        return True


@dc.dataclass(frozen=True)
class OscillatorController:
    config: DeviceConfig
    oscillator: Oscillator

    players: dict[int, OscillatorPlayer] = dc.field(default_factory=dict)

    def start(self, note_number: int, frequency: float) -> bool:
        if note_number in self.players:
            return False
        assert self.config.samplerate is not None
        period = self.config.samplerate / frequency
        op = OscillatorPlayer(self.config, self.oscillator, Sound(period))
        Thread(target=op.run).start()
        self.players[note_number] = op
        return True

    def stop(self, note_number: int) -> bool:
        op = self.players.pop(note_number, None)
        if op is not None:
            op.stop()
        return bool(op)


def demo():
    s1 = OscillatorPlayer(DeviceConfig(), Oscillator(), Sound(48_000.0 / 440.0))
    s2 = OscillatorPlayer(DeviceConfig(), Oscillator(), Sound(48_000.0 / 660.0))

    def target():
        time.sleep(0.5)
        s2.run()

    Thread(target=s1.run).start()
    Thread(target=target).start()
    time.sleep(1.5)
    s1.stop()
    s2.stop()


# class Synth(Protocol):
#     def __call__(self, out: Data, offset: Number, sound: Sound) -> None: ...
#
# @dc.dataclass
# class SynthDevice:
#     synth: Synth
#     config: DeviceConfig


if __name__ == "__main__":
    demo()
