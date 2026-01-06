from __future__ import annotations

import dataclasses as dc
from abc import ABC, abstractmethod
from contextlib import suppress
from functools import cached_property
import numbers
from queue import Queue
from threading import Lock
from typing import Any, Callable, Protocol, TypeAlias

import numpy as np

from . import Data, DeviceConfig
from .player import Player

if True:
    Number: TypeAlias = int | float
else:
    Number: TypeAlias = numbers.Number


@dc.dataclass(frozen=True)
class SoundDesc:
    period: Number
    intensity: Number = 1.0


class Synth(Protocol):
    def __call__(self, out: Data, offset: Number, desc: SoundDesc) -> None: ...


Function: TypeAlias = Callable[..., Any]


@dc.dataclass(frozen=True)
class Periodic(Synth):
    function: Function = np.sin
    period: Number = 2 * np.pi

    def __call__(self, out: Data, offset: Number, desc: SoundDesc) -> None:
        start = offset % desc.period
        end = start + len(out)
        ratio = self.period / desc.period
        wave = np.linspace(start * ratio, end * ratio, len(out))
        wave = self.function(wave, out=wave)

        intensity = desc.intensity
        with suppress(ValueError):
            # Scale up from [-1, 1] for int types only
            intensity *= np.iinfo(out.dtype).max
        wave *= intensity

        out[:] = np.asarray(wave, dtype=out.dtype)


@dc.dataclass
class SynthPlayer(Player, ABC):
    config: DeviceConfig
    desc: SoundDesc
    synth: Synth

    @classmethod
    def make(
        cls,
        config: DeviceConfig,
        synth: Synth,
        frequency: Number,
        intensity: Number = 0.75,
    ) -> SynthPlayer:
        period = config.sample_rate / frequency
        return cls(config, SoundDesc(period, intensity), synth)

    @abstractmethod
    def _fill(self, out: Data) -> bool: ...


class SimpleSynthPlayer(SynthPlayer):
    def _fill(self, out: Data) -> bool:
        self.synth(out, self.frame_count, self.desc)
        return True


if __name__ == "__main__":
    pass


class BufferedSynthPlayer(SynthPlayer):
    buffers_computed = 0
    buffer_count = 3

    @cached_property
    def empty_buffers(self) -> list[Data]:
        assert self.frame_size
        size = self.frame_size, self.config.channels
        return [np.empty(size) for _ in range(self.buffer_count)]

    @cached_property
    def full_buffers(self) -> list[Data]:
        return []

    @cached_property
    def lock(self) -> Lock:
        return Lock()

    @cached_property
    def queue(self) -> Queue[bool]:
        return Queue()

    _offset: int = 0

    def _fill_XXX(self, out: Data) -> bool:
        with self.lock:
            if not self.empty_buffers:
                return False
            data = self.empty_buffers.pop()
            self.full_buffers.insert(0, data)
            self.buffers_computed += 1
        self._fill(data)
        return True

    def _target(self) -> None:
        # while self._queue:
        pass
