from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel, Field

from ..scale.number import NoteNumber
from .polyphony import Polyphony
from .voice import Voice, VoiceState


class NotePress(BaseModel, frozen=True):
    note_number: NoteNumber
    is_press: bool = True

    def __init__(self, note_number: NoteNumber, is_press: bool = True) -> None:
        super().__init__(note_number=note_number, is_press=is_press)


class Mixer(BaseModel):
    voice_maker: Callable[[NoteNumber], Voice]
    channels: int = 1
    polyphony: Polyphony = Field(default_factory=Polyphony)
    synchronize_oscillators: bool = False
    frame_count: int = 0
    voices: dict[NoteNumber, VoiceState] = Field(default_factory=dict)
    pressed_notes: list[NoteNumber] = Field(default_factory=list)

    def apply(self, note: NotePress) -> bool:
        note_number = note.note_number
        if note.is_press:
            if note_number in self.voices:
                return False
            voice = self.voice_maker(note_number)
            voice_count = _voice_count(voice)
            while (
                self.pressed_notes
                and self._pressed_voice_count() + voice_count
                > self.polyphony.max_voices
            ):
                self._release_oldest()
            phase = self.frame_count % voice.period_samples
            self.voices[note_number] = VoiceState(
                voice=voice,
                phase=phase if self.synchronize_oscillators else 0,
            )
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

    def _release_oldest(self) -> None:
        note_number = self.pressed_notes.pop(0)
        voice = self.voices[note_number]
        voice.release()
        if voice.complete:
            self.voices.pop(note_number)

    def _pressed_voice_count(self) -> int:
        return sum(
            _voice_count(self.voices[note_number].voice)
            for note_number in self.pressed_notes
        )

    def render(
        self,
        frame_size: int,
        dtype: DTypeLike = float,
        channels: int | None = None,
    ) -> np.ndarray:
        channel_count = self.channels if channels is None else channels
        mixed = np.zeros((frame_size, channel_count))
        for note_number, voice in tuple(self.voices.items()):
            rendered = voice.render(frame_size)
            if rendered.ndim == 1:
                mixed += rendered[:, np.newaxis]
            elif rendered.shape[1] == channel_count:
                mixed += rendered
            elif channel_count == 1:
                mixed += rendered.mean(axis=1)[:, np.newaxis]
            else:
                mixed += rendered[:, :1]
            if voice.complete:
                self.voices.pop(note_number)
        mixed /= self.polyphony.headroom

        self.frame_count += frame_size
        return mixed.astype(dtype, copy=False)


def _voice_count(voice: Voice) -> int:
    return 2 if voice.binaural.enable else 1
