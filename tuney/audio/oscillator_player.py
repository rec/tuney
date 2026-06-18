from __future__ import annotations

from functools import cached_property, wraps
from typing import Any

import numpy as np

from .player import Player
from .voice import Voice, VoiceState


class OscillatorPlayer(Player):
    sound: Voice = Voice()

    @cached_property
    def voice(self) -> VoiceState:
        return VoiceState(voice=self.sound)

    def stop(self) -> None:
        self.voice.release()
        if self.voice.complete:
            super().stop()

    def _fill(self, out: np.ndarray) -> bool | None:
        wave = self.voice.render(len(out))
        wave = wave.reshape((len(wave), 1))
        out[:] = np.asarray(wave, dtype=out.dtype)
        if self.voice.complete:
            super().stop()
            return False
        return True


@wraps(OscillatorPlayer.__init__)
def run(*args: Any, **kwargs: Any) -> None:
    o = OscillatorPlayer(*args, **kwargs)
    o.run()
