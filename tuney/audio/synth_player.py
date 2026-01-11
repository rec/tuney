from __future__ import annotations

import dataclasses as dc
import datetime
import time
from contextlib import suppress
from threading import Thread
from typing import Any, Callable, TypeAlias

import numpy as np

from .device_config import DeviceConfig
from ..note import NoteOctave
from .player import Player
from .sample_data import Data

Number: TypeAlias = int | float
Function: TypeAlias = Callable[..., Any]

INTENSITY = 0.1
FADE = 0  # 0x40000


# TODO: relieve the tension between human units (frequency, time) and sample units.
@dc.dataclass(frozen=True)
class Sound:
    period: Number = 0x100
    intensity: Number = INTENSITY
    fade_in_samples: Number = 0x1000
    fade_out_samples: Number = 0x1000


@dc.dataclass(frozen=True)
class Oscillator:
    function: Function = np.sin
    period: Number = 2 * np.pi


@dc.dataclass
class OscillatorPlayer(Player):
    sound: Sound = dc.field(default_factory=Sound)
    oscillator: Oscillator = dc.field(default_factory=Oscillator)

    _stopping: bool = False

    #: Records the the frame we started to fade out.
    _fade_frame: Number | None = None

    def stop(self) -> None:
        if self.sound.fade_out_samples > 0:
            self._stopping = True
        else:
            super().stop()

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

        def clamp(x: float) -> float:
            return max(0.0, min(1.0, x))

        def fade(wave: np.ndarray, start: float, length: float) -> None:
            wave *= np.linspace(clamp(start), clamp(start + length), len(wave))

        fade_in = self.sound.fade_in_samples
        if self.frame_count < fade_in and not self._stopping:
            fade(wave, self.frame_count / fade_in, len(out) / fade_in)

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

            fade(wave, start, -len(out) / fade_out)

        wave = wave.reshape((len(wave), 1))
        out[:] = np.asarray(wave, dtype=out.dtype)
        return True


@dc.dataclass(frozen=True)
class OscillatorController:
    config: DeviceConfig = dc.field(default_factory=DeviceConfig)
    oscillator: Oscillator = dc.field(default_factory=Oscillator)
    players: dict[int, OscillatorPlayer] = dc.field(default_factory=dict)

    def start(self, note: NoteOctave) -> bool:
        if note.note_number in self.players:
            return False
        # assert self.config.samplerate is not None
        period = (self.config.samplerate or 48_000) / note.frequency
        op = OscillatorPlayer(
            config=self.config, oscillator=self.oscillator, sound=Sound(period)
        )
        Thread(target=op.run).start()
        self.players[note.note_number] = op
        return True

    def stop(self, note: NoteOctave) -> bool:
        if (op := self.players.pop(note.note_number, None)) is not None:
            op.stop()
        return bool(op)  # pyrefly: ignore[unbound-name]

    def stop_all(self) -> None:
        for player in self.players.values():
            player.stop()
        self.players.clear()


def _timestamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def demo():
    from ..note import NoteOctave

    oc = OscillatorController()

    DT = 0.2

    stack = []
    o1 = "C4", "E4", "D5", "Eb3", "G3", "C3", "E3", "D4", "Eb2", "G2"
    o2 = "C2", "E2", "D3", "Eb1", "G1", "C1", "E1", "D2", "Eb0", "G0"

    o1 = "C3", "E3", "D4", "Eb2", "G2"
    o2 = "C1", "E1", "D2", "Eb0", "G0"
    for note in (o1 + o2)[0]:
        print("on", note)
        stack.append(NoteOctave.from_name(note))
        if not oc.start(stack[-1]):
            print("oops", stack[-1])
        time.sleep(DT)

    while stack:
        note = stack.pop()
        print("off", _timestamp(), note)
        if not oc.stop(note):
            print("oops off", note)
        time.sleep(DT / 2)


def demo1():
    s1 = OscillatorPlayer(sound=Sound(48_000.0 / 440.0))
    s2 = OscillatorPlayer(sound=Sound(48_000.0 / 660.0))

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
