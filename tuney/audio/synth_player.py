from __future__ import annotations

import dataclasses as dc
from abc import ABC, abstractmethod
from functools import cached_property
from queue import Queue
from threading import Lock
from typing import Protocol

import numpy as np

from . import Data, DeviceConfig
from .player import Player


class Synthesis(Protocol):
    def __call__(self, out: Data, sample_offset: int) -> None: ...


@dc.dataclass(frozen=True)
class Update:
    frame_count: int
    offset: int

    def __int__(self) -> int:
        return self.frame_count + self.offset


class SynthPlayer(Player, ABC):
    def __init__(
        self, synthesis: Synthesis, config: DeviceConfig, buffer_count: int = 3
    ) -> None:
        super().__init__()
        self.config = config
        self.synthesis = synthesis

    @abstractmethod
    def _fill(self, out: Data) -> bool: ...


class SimpleSynthPlayer(SynthPlayer):
    def _fill(self, out: Data) -> bool:
        self.synthesis(out, self.frame_count)
        return True


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


#    @abstractmethod
#   def fill(self,
