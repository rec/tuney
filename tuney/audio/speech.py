from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel, ConfigDict

from ..app.platform_info import report_error

BASE_SPEECH_RATE = 50
PHRASE_PUNCTUATION = '.:;!?'


class SpeechPlayback(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: np.ndarray
    level: float
    position: int = 0

    @property
    def complete(self) -> bool:
        return self.position >= len(self.data)

    def render(self, frame_size: int, dtype: DTypeLike, channels: int) -> np.ndarray:
        end = self.position + frame_size
        out = self.data[self.position : end]
        self.position = end
        if len(out) < frame_size:
            pad = np.zeros((frame_size - len(out), out.shape[1]))
            out = np.concatenate([out, pad])
        if out.shape[1] != channels:
            out = np.repeat(out.mean(axis=1)[:, np.newaxis], channels, axis=1)
        return (out * self.level).astype(dtype, copy=False)


class SpeechPhrase(BaseModel, frozen=True):
    text: str
    start: float


class SpeechRequest(BaseModel, frozen=True):
    phrases: list[SpeechPhrase]
    sample_rate: int
    level: float
    voice: str | None


def render_speech(
    request: SpeechRequest,
) -> SpeechPlayback | None:
    phrases = request.phrases
    if not phrases:
        return None
    with TemporaryDirectory() as directory:
        rendered = _render_phrases(Path(directory), phrases, request.voice)
        if not rendered:
            return None
        return SpeechPlayback(
            data=_align_phrases(rendered, request.sample_rate),
            level=request.level,
        )


class _SpeechFile(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: np.ndarray
    sample_rate: int


class _SpeechEngine(Protocol):
    def getProperty(self, name: str) -> list[object]: ...

    def setProperty(self, name: str, value: object) -> None: ...


def voice_names() -> list[str]:
    import pyttsx3

    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
    except (OSError, RuntimeError) as error:
        report_error(f'Could not list speech voices: {error}')
        return []
    return sorted(
        str(name)
        for voice in voices
        if (name := getattr(voice, 'name', None)) is not None
    )


def _render_speech(
    text: str, rate: int, path: Path, voice: str | None
) -> _SpeechFile | None:
    import pyttsx3
    import soundfile

    engine = pyttsx3.init()
    engine.setProperty('rate', rate)
    if voice is not None:
        _set_voice(engine, voice)
    engine.save_to_file(text, str(path))
    engine.runAndWait()
    if not path.exists():
        return None
    data, sample_rate = soundfile.read(path, always_2d=True)
    return _SpeechFile(data=data, sample_rate=sample_rate)


def _set_voice(engine: _SpeechEngine, name: str) -> None:
    for voice in engine.getProperty('voices'):
        voice_id = getattr(voice, 'id', None)
        if getattr(voice, 'name', None) == name or voice_id == name:
            engine.setProperty('voice', voice_id)
            return


def _render_phrases(
    directory: Path, phrases: list[SpeechPhrase], voice: str | None
) -> list[tuple[SpeechPhrase, _SpeechFile]]:
    rendered = []
    for i, phrase in enumerate(phrases):
        path = directory / f'phrase-{i}.wav'
        if speech_file := _render_speech(phrase.text, BASE_SPEECH_RATE, path, voice):
            rendered.append((phrase, speech_file))
    return rendered


def _align_phrases(
    rendered: list[tuple[SpeechPhrase, _SpeechFile]], sample_rate: int
) -> np.ndarray:
    resampled = [
        (phrase, _resample(speech_file, sample_rate))
        for phrase, speech_file in rendered
    ]
    channels = max(data.shape[1] for _, data in resampled)
    length = max(
        round(phrase.start * sample_rate) + len(data) for phrase, data in resampled
    )
    out = np.zeros((length, channels))
    for phrase, data in resampled:
        start = round(phrase.start * sample_rate)
        end = start + len(data)
        if data.shape[1] != channels:
            data = np.repeat(data.mean(axis=1)[:, np.newaxis], channels, axis=1)
        out[start:end] += data
    return out


def _resample(speech_file: _SpeechFile, sample_rate: int) -> np.ndarray:
    if speech_file.sample_rate == sample_rate:
        return speech_file.data
    old = np.arange(len(speech_file.data))
    new_count = round(len(speech_file.data) * sample_rate / speech_file.sample_rate)
    new = np.linspace(0, len(speech_file.data) - 1, new_count)
    return np.stack(
        [
            np.interp(new, old, speech_file.data[:, i])
            for i in range(speech_file.data.shape[1])
        ],
        axis=1,
    )
