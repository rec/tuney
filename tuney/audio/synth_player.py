from __future__ import annotations

import dataclasses as dc
import numbers
import time
from contextlib import suppress
from threading import Thread
from typing import Any, Callable, Protocol, TypeAlias

import numpy as np

from .device_config import DeviceConfig
from .playback import Data
from .player import Player

if True:
    Number: TypeAlias = int | float
else:
    Number: TypeAlias = numbers.Number

INTENSITY = 0.1


@dc.dataclass(frozen=True)
class Sound:
    period: Number
    intensity: Number = INTENSITY


class Synth(Protocol):
    def __call__(self, out: Data, offset: Number, sound: Sound) -> None: ...


@dc.dataclass
class SynthDevice:
    synth: Synth
    config: DeviceConfig


Function: TypeAlias = Callable[..., Any]


@dc.dataclass(frozen=True)
class Oscillator:
    function: Function = np.sin
    period: Number = 2 * np.pi


@dc.dataclass(frozen=True)
class OscillatorSound(Player):
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


@dc.dataclass
class SynthPlayer(Player):
    config: DeviceConfig
    sound: Sound
    synth: Synth

    @classmethod
    def make(
        cls,
        config: DeviceConfig,
        synth: Synth,
        frequency: Number,
        intensity: Number = INTENSITY,
    ) -> SynthPlayer:
        assert config.samplerate is not None
        period = config.samplerate / frequency
        return cls(config, Sound(period, intensity), synth)


class MultiPlayer:
    synth: SynthPlayer  # Just to make copies of


def demo():
    s1 = SynthPlayer(DeviceConfig(), Sound(48_000.0 / 440.0), Oscillator())
    s2 = SynthPlayer(DeviceConfig(), Sound(48_000.0 / 660.0), Oscillator())

    def target():
        time.sleep(0.5)
        s2.run()

    Thread(target=s1.run).start()
    Thread(target=target).start()
    time.sleep(1.5)
    s1.stop()
    s2.stop()


if __name__ == "__main__":
    demo()
