from __future__ import annotations

from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

import numpy as np
from numpy.typing import DTypeLike
from pydantic import BaseModel, ConfigDict, Field
from reccy.configuration.units import Seconds

from ..app.platform_info import report_error

BASE_SPEECH_RATE = 200
PHRASE_PUNCTUATION = '.:;!?'
SPEECH_BLOCK_FRAMES = 8192


class SpeechSegment(BaseModel, frozen=True):
    start: int
    data: np.ndarray

    @property
    def end(self) -> int:
        return self.start + len(self.data)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SpeechPlayback(BaseModel):
    segments: list[SpeechSegment]
    level: float
    position: int = 0
    next_segment: int = 0
    active_segments: list[int] = Field(default_factory=list)
    temporary: TemporaryDirectory[str] | None = Field(default=None, exclude=True)

    @cached_property
    def total_frames(self) -> int:
        return max((s.end for s in self.segments), default=0)

    @property
    def complete(self) -> bool:
        return self.position >= self.total_frames

    def render(self, frame_size: int, dtype: DTypeLike, channels: int) -> np.ndarray:
        end = self.position + frame_size
        out = np.zeros((frame_size, channels), dtype=np.float64)
        while (
            self.next_segment < len(self.segments)
            and self.segments[self.next_segment].start < end
        ):
            self.active_segments.append(self.next_segment)
            self.next_segment += 1
        remaining = []
        for index in self.active_segments:
            segment = self.segments[index]
            if segment.end <= self.position:
                continue
            start = max(self.position, segment.start)
            finish = min(end, segment.end)
            data = segment.data[start - segment.start : finish - segment.start]
            if data.shape[1] != channels:
                data = np.repeat(data.mean(axis=1)[:, np.newaxis], channels, axis=1)
            out[start - self.position : finish - self.position] += data
            if segment.end > end:
                remaining.append(index)
        self.active_segments = remaining
        self.position = end
        return (out * self.level).astype(dtype, copy=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SpeechPhrase(BaseModel, frozen=True):
    text: str
    start: Seconds


class SpeechRequest(BaseModel, frozen=True):
    phrases: list[SpeechPhrase]
    sample_rate: int
    level: float
    speed: float
    voice: str | None


def render_speech(
    request: SpeechRequest,
) -> SpeechPlayback | None:
    if not request.phrases:
        return None
    temporary = TemporaryDirectory(prefix='tuney-speech-')
    playback = None
    try:
        segments = []
        for index, phrase in enumerate(request.phrases):
            path = Path(temporary.name) / f'phrase-{index}.wav'
            if speech_file := _render_speech(
                phrase.text, BASE_SPEECH_RATE, path, request.voice
            ):
                if speech_file.frames == 0:
                    continue
                data = _resample_file(
                    speech_file,
                    Path(temporary.name) / f'phrase-{index}.npy',
                    request.sample_rate,
                    request.speed,
                )
                segments.append(
                    SpeechSegment(
                        start=round(phrase.start * request.sample_rate), data=data
                    )
                )
                path.unlink()
        if segments:
            playback = SpeechPlayback(
                segments=sorted(segments, key=lambda s: s.start),
                level=request.level,
                temporary=temporary,
            )
        return playback
    finally:
        if playback is None:
            temporary.cleanup()


class _SpeechFile(BaseModel):
    path: Path
    sample_rate: int
    frames: int
    channels: int


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
    info = soundfile.info(path)
    return _SpeechFile(
        path=path,
        sample_rate=info.samplerate,
        frames=info.frames,
        channels=info.channels,
    )


def _set_voice(engine: _SpeechEngine, name: str) -> None:
    for voice in engine.getProperty('voices'):
        voice_id = getattr(voice, 'id', None)
        if getattr(voice, 'name', None) == name or voice_id == name:
            engine.setProperty('voice', voice_id)
            return


def _resample_file(
    speech_file: _SpeechFile, path: Path, sample_rate: int, speed: float
) -> np.ndarray:
    import soundfile

    scaled_frames = max(1, round(speech_file.frames / speed))
    frames = max(1, round(scaled_frames * sample_rate / speech_file.sample_rate))
    data = np.lib.format.open_memmap(
        path, mode='w+', dtype=np.float64, shape=(frames, speech_file.channels)
    )
    source_step = (speech_file.frames - 1) / max(1, frames - 1)
    block_size = max(
        1, min(SPEECH_BLOCK_FRAMES, round(SPEECH_BLOCK_FRAMES / max(1, source_step)))
    )
    with soundfile.SoundFile(speech_file.path) as source:
        for start in range(0, frames, block_size):
            end = min(frames, start + block_size)
            positions = np.arange(start, end) * source_step
            source_start = int(positions[0])
            source_end = min(speech_file.frames, int(np.ceil(positions[-1])) + 1)
            source.seek(source_start)
            samples = source.read(source_end - source_start, always_2d=True)
            source_positions = np.arange(source_start, source_start + len(samples))
            for channel in range(speech_file.channels):
                data[start:end, channel] = np.interp(
                    positions, source_positions, samples[:, channel]
                )
    data.flush()
    return data
