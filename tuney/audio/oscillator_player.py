from __future__ import annotations

import dataclasses as dc
from contextlib import suppress
from functools import cached_property
from typing import cast

import numpy as np

from ..types import Data, Number
from . import oscillator as osc
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


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _fade(wave: Data, start: float, length: float) -> None:
    wave *= np.linspace(_clamp(start), _clamp(start + length), len(wave))
