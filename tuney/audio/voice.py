from __future__ import annotations

from fractions import Fraction
from functools import cached_property

from enge.synth import PreparedVoice
from pydantic import BaseModel, Field, field_validator
from reccy.configuration.units import Hertz, Seconds
from ufor.envelope import Envelope, Segment

from .oscillator import Oscillator
from .sound import Binaural

DEFAULT_FADE: Seconds = 0x1000 / 48_000


class Voice(BaseModel, frozen=True):
    frequency: Hertz = 48_000 / 0x100
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
    def definition(self) -> PreparedVoice:
        frequencies = [self.frequency]
        routes = [[1.0]]
        if self.binaural.enable:
            beat = self.binaural.frequency / 2
            frequencies = [self.frequency - beat, self.frequency + beat]
            near = (1 + self.binaural.width) / 2
            far = (1 - self.binaural.width) / 2
            routes = [[near, far], [far, near]]
        return PreparedVoice(
            sample_rate=self.sample_rate,
            oscillator=self.oscillator.definition,
            envelope=Envelope(
                segments=[Segment(duration=Fraction(str(self.fade_in)), target=1)],
                release=[Segment(duration=Fraction(str(self.fade_out)), target=0)],
            ),
            frequencies=frequencies,
            routes=routes,
            gain=self.gain,
            minimum_hold_seconds=Fraction(str(self.minimum_note_time)),
        )
