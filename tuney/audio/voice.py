from __future__ import annotations

from functools import cached_property

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..time import Seconds
from .oscillator import Oscillator
from .sound import Binaural

DEFAULT_FADE: Seconds = 0x1000 / 48_000


class Voice(BaseModel, frozen=True):
    frequency: float = 48_000 / 0x100
    gain: float = 1.0
    fade_in: Seconds = DEFAULT_FADE
    fade_out: Seconds = DEFAULT_FADE
    minimum_note_time: Seconds = 0.5
    oscillator: Oscillator = Field(default_factory=Oscillator)
    sample_rate: int = 48_000
    binaural: Binaural = Field(default_factory=Binaural)

    @field_validator('binaural')
    @classmethod
    def _copy_binaural(cls, binaural: Binaural) -> Binaural:
        return binaural.model_copy()

    @cached_property
    def period(self) -> float:
        return 1 / self.frequency

    @cached_property
    def period_samples(self) -> float:
        return self.period * self.sample_rate

    @cached_property
    def binaural_period_samples(self) -> np.ndarray:
        beat = self.binaural.frequency / 2
        frequencies = np.array([self.frequency - beat, self.frequency + beat])
        return self.sample_rate / frequencies

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
    model_config = ConfigDict(arbitrary_types_allowed=True)

    voice: Voice
    phase: float | np.ndarray = 0
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
            shape = (frame_size, 2) if self.voice.binaural.enable else frame_size
            return np.zeros(shape)

        period_samples: float | np.ndarray
        period_samples = (
            self.voice.binaural_period_samples
            if self.voice.binaural.enable
            else self.voice.period_samples
        )
        wave = self.voice.oscillator(self.phase, frame_size, period_samples).astype(
            float, copy=False
        )
        frames = self.frame_count + np.arange(frame_size)
        if self.voice.binaural.enable:
            wave = self._binaural_wave(wave)
            envelope = self._envelope(frames)
            if isinstance(envelope, int):
                envelope = np.full(frame_size, envelope)
            envelope = envelope[:, np.newaxis]
        else:
            envelope = self._envelope(frames)
        wave *= envelope * self.voice.gain

        self.phase = (self.phase + frame_size) % period_samples
        self.frame_count += frame_size
        if self.release_frame is not None:
            last_sample = self.release_frame + self.voice.fade_out_samples
            self.complete = self.frame_count >= last_sample
        return wave

    def _binaural_wave(self, wave: np.ndarray) -> np.ndarray:
        width = self.voice.binaural.width
        low_left = (1 + width) / 2
        high_left = (1 - width) / 2
        low_right = high_left
        high_right = low_left
        return np.column_stack(
            [
                wave[:, 0] * low_left + wave[:, 1] * high_left,
                wave[:, 0] * low_right + wave[:, 1] * high_right,
            ]
        )

    def _envelope(self, frames: np.ndarray) -> np.ndarray | int:
        if self.voice.fade_in_samples <= 0:
            fade_in: np.ndarray | int = 1
        else:
            fade_in = np.clip(frames / self.voice.fade_in_samples, 0, 1)

        if self.release_frame is None:
            return fade_in
        if self.voice.fade_out_samples <= 0:
            return fade_in * (frames < self.release_frame)

        elapsed = 1 - (frames - self.release_frame) / self.voice.fade_out_samples
        fade_out = self.release_gain * np.clip(elapsed, 0, 1)
        return np.minimum(fade_in, fade_out)
