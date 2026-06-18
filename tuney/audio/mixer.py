from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel, Field

from ..types import NoteNumber
from .voice import Voice, VoiceState


class NotePress(BaseModel, frozen=True):
    note_number: NoteNumber
    is_press: bool


class Mixer(BaseModel):
    sound: Callable[[NoteNumber], Voice]
    channels: int = 1
    polyphonic_headroom: float = Field(4, gt=0)
    max_polyphony: int = Field(32, gt=0)
    voices: dict[NoteNumber, VoiceState] = Field(default_factory=dict)
    pressed_notes: list[NoteNumber] = Field(default_factory=list)

    def apply(self, note: NotePress) -> bool:
        note_number = note.note_number
        if note.is_press:
            if (
                note_number in self.voices
                or len(self.pressed_notes) >= self.max_polyphony
            ):
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

    def render(
        self,
        frame_size: int,
        dtype: DTypeLike = float,
        channels: int | None = None,
    ) -> np.ndarray:
        mixed = np.zeros(frame_size)
        for note_number, voice in tuple(self.voices.items()):
            mixed += voice.render(frame_size)
            if voice.complete:
                self.voices.pop(note_number)
        mixed /= self.polyphonic_headroom
        np.clip(mixed, -1, 1, out=mixed)

        channel_count = self.channels if channels is None else channels
        return np.repeat(mixed[:, np.newaxis], channel_count, axis=1).astype(
            dtype, copy=False
        )
