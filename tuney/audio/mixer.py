from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel, Field

from ..types import NoteNumber
from .player import MASTER_GAIN
from .voice import Voice, VoiceState


class NoteEvent(BaseModel, frozen=True):
    note_number: NoteNumber
    is_press: bool


class Mixer(BaseModel):
    sound: Callable[[NoteNumber], Voice]
    channels: int = 1
    voices: dict[NoteNumber, VoiceState] = Field(default_factory=dict)
    pressed_notes: list[NoteNumber] = Field(default_factory=list)

    def apply(self, event: NoteEvent) -> bool:
        note_number = event.note_number
        if event.is_press:
            if note_number in self.voices:
                return False
            self.voices[note_number] = VoiceState(voice=self.sound(note_number))
            self.pressed_notes.append(note_number)
            return True

        if note_number not in self.pressed_notes:
            return False
        self.pressed_notes.remove(note_number)
        voice = self.voices[note_number]
        voice.release()
        if voice.complete:
            self.voices.pop(note_number)
        return True

    def stop_all(self) -> None:
        self.pressed_notes.clear()
        for voice in self.voices.values():
            voice.release()

    def render(self, frame_size: int, dtype: DTypeLike = float) -> np.ndarray:
        mixed = np.zeros(frame_size)
        for note_number, voice in tuple(self.voices.items()):
            mixed += voice.render(frame_size)
            if voice.complete:
                self.voices.pop(note_number)
        mixed *= MASTER_GAIN

        out = np.empty((frame_size, self.channels), dtype=dtype)
        out[:] = mixed[:, np.newaxis]
        return out
