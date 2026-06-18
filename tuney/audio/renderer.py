from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel, Field

from ..types import NoteNumber
from .oscillator import Oscillator
from .oscillator_player import OscillatorPlayer, Sound


class NoteEvent(BaseModel, frozen=True):
    note_number: NoteNumber
    is_press: bool


class OfflineRenderer(BaseModel):
    sound: Callable[[NoteNumber], Sound]
    oscillator: Oscillator = Oscillator()
    channels: int = 1
    players: dict[NoteNumber, OscillatorPlayer] = Field(default_factory=dict)
    pressed_notes: list[NoteNumber] = Field(default_factory=list)

    def apply(self, event: NoteEvent) -> bool:
        note_number = event.note_number
        if event.is_press:
            if note_number in self.players:
                return False
            self.players[note_number] = OscillatorPlayer(
                oscillator=self.oscillator,
                sound=self.sound(note_number),
            )
            self.pressed_notes.append(note_number)
            return True

        if note_number not in self.pressed_notes:
            return False
        self.pressed_notes.remove(note_number)
        player = self.players[note_number]
        player.stop()
        if player.sound.fade_out_samples <= 0:
            self.players.pop(note_number)
        return True

    def stop_all(self) -> None:
        self.pressed_notes.clear()
        for player in self.players.values():
            player.stop()
        self.players.clear()

    def render(
        self,
        events: Sequence[NoteEvent],
        frame_size: int,
        dtype: DTypeLike = float,
    ) -> np.ndarray:
        for event in events:
            self.apply(event)

        out = np.zeros((frame_size, self.channels), dtype=dtype)
        for note_number, player in tuple(self.players.items()):
            voice = np.zeros_like(out)
            if player.fill(voice, frame_size):
                out += voice
            else:
                self.players.pop(note_number)
        return out
