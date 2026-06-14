from __future__ import annotations

from functools import wraps
from typing import Any

import numpy as np
from pydantic import BaseModel, PrivateAttr

from .oscillator import Oscillator
from .player import Player

FADE = 0  # 0x40000


class Sound(BaseModel, frozen=True):
    period: float = 0x100
    gain: float = 1.0
    fade_in_samples: float = 0x1000
    fade_out_samples: float = 0x1000


class OscillatorPlayer(Player):
    sound: Sound = Sound()
    oscillator: Oscillator = Oscillator()

    #: Records the the frame we started to fade out.
    _fade_frame: float | None = PrivateAttr(None)
    _stopping: bool = PrivateAttr(False)

    def stop(self) -> None:
        if self.sound.fade_out_samples > 0:
            self._stopping = True
        else:
            super().stop()

    def _fill(self, out: np.ndarray) -> bool | None:
        period = self.sound.period
        start = self.frame_count % period
        wave = self.oscillator(start, len(out), period)
        wave *= self.sound.gain

        fade_in = self.sound.fade_in_samples
        if self.frame_count < fade_in and not self._stopping:
            _fade(wave, self.frame_count / fade_in, len(out) / fade_in)

        elif self._stopping:
            if self._fade_frame is None:
                # Account for the case when we fade out before we've faded in
                offset = max(0.0, fade_in - self.frame_count)
                self._fade_frame = self.frame_count - offset

            fade_out = self.sound.fade_out_samples
            elapsed = self.frame_count - self._fade_frame
            if (start := 1 - elapsed / fade_out) <= 0:
                super().stop()
                return False

            _fade(wave, start, -len(out) / fade_out)

        wave = wave.reshape((len(wave), 1))
        out[:] = np.asarray(wave, dtype=out.dtype)
        return True


@wraps(OscillatorPlayer.__init__)
def run(*args: Any, **kwargs: Any) -> None:
    o = OscillatorPlayer(*args, **kwargs)
    o.run()


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _fade(wave: np.ndarray, start: float, length: float) -> None:
    wave *= np.linspace(
        _clamp(start), _clamp(start + length), len(wave), endpoint=False
    )
