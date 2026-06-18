from __future__ import annotations

from functools import cached_property

import numpy as np
from pydantic import BaseModel

from .oscillator import Oscillator


class Voice(BaseModel, frozen=True):
    frequency: float = 48_000 / 0x100
    gain: float = 1.0
    fade_in_samples: float = 0x1000
    fade_out_samples: float = 0x1000
    oscillator: Oscillator = Oscillator()
    sample_rate: float = 48_000

    @cached_property
    def period(self) -> float:
        return 1 / self.frequency

    @cached_property
    def sample_period(self) -> float:
        return self.sample_rate * self.period


class VoiceState(BaseModel):
    voice: Voice
    phase: float = 0
    frame_count: int = 0
    release_frame: int | None = None
    release_gain: float = 1.0
    complete: bool = False

    def release(self) -> bool:
        if self.release_frame is not None or self.complete:
            return False
        if self.voice.fade_out_samples <= 0:
            self.complete = True
        else:
            self.release_frame = self.frame_count
            self.release_gain = 1.0
            if (fade := self.voice.fade_in_samples) > 0:
                self.release_gain = min(1.0, self.frame_count / fade)
        return True

    def render(self, frame_size: int) -> np.ndarray:
        if self.complete:
            return np.zeros(frame_size)

        sample_period = self.voice.sample_period
        wave = self.voice.oscillator(self.phase, frame_size, sample_period)
        frames = self.frame_count + np.arange(frame_size)
        wave *= self._envelope(frames) * self.voice.gain

        self.phase = (self.phase + frame_size) % sample_period
        self.frame_count += frame_size
        if self.release_frame is not None:
            last_sample = self.release_frame + self.voice.fade_out_samples
            self.complete = self.frame_count >= last_sample
        return wave

    def _envelope(self, frames: np.ndarray) -> np.ndarray | int:
        if self.voice.fade_out_samples <= 0:
            return 1
        if self.release_frame is not None:
            elapsed = frames - self.release_frame
            samples = 1 - elapsed / self.voice.fade_out_samples
            return self.release_gain * np.clip(samples, 0, 1)
        if self.voice.fade_in_samples <= 0:
            return 1
        return np.clip(frames / self.voice.fade_in_samples, 0, 1)
