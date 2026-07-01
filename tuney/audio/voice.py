from __future__ import annotations

from functools import cached_property

import numpy as np
from pydantic import BaseModel

from ..time import Seconds
from .oscillator import Oscillator

DEFAULT_FADE: Seconds = 0x1000 / 48_000


class Voice(BaseModel, frozen=True):
    frequency: float = 48_000 / 0x100
    gain: float = 1.0
    fade_in: Seconds = DEFAULT_FADE
    fade_out: Seconds = DEFAULT_FADE
    minimum_note_time: Seconds = 0.5
    oscillator: Oscillator = Oscillator()
    sample_rate: float = 48_000

    @cached_property
    def period(self) -> float:
        return 1 / self.frequency

    @cached_property
    def sample_period(self) -> float:
        return self.sample_rate * self.period

    @cached_property
    def fade_in_samples(self) -> float:
        return self.fade_in * self.sample_rate

    @cached_property
    def fade_out_samples(self) -> float:
        return self.fade_out * self.sample_rate

    @cached_property
    def minimum_note_samples(self) -> float:
        return self.minimum_note_time * self.sample_rate


class VoiceState(BaseModel):
    voice: Voice
    phase: float = 0
    frame_count: int = 0
    release_frame: float | None = None
    release_gain: float = 1.0
    complete: bool = False

    def release(self) -> bool:
        if self.release_frame is not None or self.complete:
            return False
        self.release_frame = max(self.frame_count, self.voice.minimum_note_samples)
        if self.voice.fade_out_samples <= 0 and self.release_frame <= self.frame_count:
            self.complete = True
        else:
            self.release_gain = 1.0
            if (fade := self.voice.fade_in_samples) > 0:
                self.release_gain = min(1.0, self.release_frame / fade)
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
        if self.voice.fade_in_samples <= 0:
            fade_in: np.ndarray | int = 1
        else:
            fade_in = np.clip(frames / self.voice.fade_in_samples, 0, 1)

        if self.release_frame is None:
            return fade_in
        if self.voice.fade_out_samples <= 0:
            return fade_in * (frames < self.release_frame)

        elapsed = frames - self.release_frame
        fade_out = self.release_gain * np.clip(
            1 - elapsed / self.voice.fade_out_samples, 0, 1
        )
        return np.minimum(fade_in, fade_out)
