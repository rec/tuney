from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import tomlkit

from ..config.serialize import serialize
from ..presets import merged_data, read_preset
from .mixer import Mixer, NotePress
from .speech import SpeechPhrase, SpeechRequest, render_speech

if TYPE_CHECKING:
    import soundfile

    from ..app.app import App
    from .player import Player


SILENCE_BEFORE_PRESET_SECONDS = 1
SILENCE_AFTER_NAME_SECONDS = 2
SILENCE_AFTER_PHRASE_SECONDS = 1
BLOCK_SIZE = 1024


def render_test_sheet(path: Path, app: App, preset_names: Sequence[str]) -> None:
    import soundfile

    presets = [_preset_app(app, name) for name in preset_names]
    sample_rate = app.player.sample_rate
    channels = max([app.player.channels] + [i.player.channels for i in presets])
    start_time = datetime.now(timezone.utc)
    with soundfile.SoundFile(
        path,
        mode='w',
        samplerate=sample_rate,
        channels=channels,
    ) as file:
        _set_comment(file, app, preset_names, start_time)
        for preset in presets:
            _write_silence(file, sample_rate, channels, SILENCE_BEFORE_PRESET_SECONDS)
            _write_preset_name(file, preset, sample_rate, channels)
            _write_silence(file, sample_rate, channels, SILENCE_AFTER_NAME_SECONDS)
            _write_note_events(
                file,
                preset.player,
                preset.note_events(sample_rate),
                sample_rate,
                channels,
            )
            _write_silence(file, sample_rate, channels, SILENCE_AFTER_PHRASE_SECONDS)
        _set_comment(file, app, preset_names, start_time)


def _preset_app(app: App, name: str) -> App:
    data = merged_data(
        app.dump_data(), read_preset(name), {'preset': name, 'gui': False}
    )
    return type(app).model_validate(data)


def _write_silence(
    file: soundfile.SoundFile, sample_rate: int, channels: int, seconds: int
) -> None:
    file.write(np.zeros((seconds * sample_rate, channels), dtype=np.float32))


def _write_preset_name(
    file: soundfile.SoundFile, app: App, sample_rate: int, channels: int
) -> None:
    request = SpeechRequest(
        phrases=[SpeechPhrase(text=app.preset or '', start=0)],
        sample_rate=sample_rate,
        level=app.speech_level,
        speed=app.speech_speed,
        voice=app.speech_voice,
    )
    if speech := render_speech(request):
        file.write(_channels(speech.data * speech.level, channels))


def _write_note_events(
    file: soundfile.SoundFile,
    player: Player,
    events: list[tuple[int, NotePress]],
    sample_rate: int,
    channels: int,
) -> None:
    mixer = Mixer(
        voice_maker=partial(player.voice_maker, sample_rate=sample_rate),
        channels=channels,
        polyphony=player.sound.polyphony,
        synchronize_oscillators=player.sound.synchronize_oscillators,
    )
    rendered = 0
    for frame, note in events:
        if frame > rendered:
            file.write(
                _mastered(
                    mixer.render(frame - rendered, np.float32, channels),
                    player.output_gain,
                )
            )
            rendered = frame
        mixer.apply(note)

    mixer.stop_all()
    while mixer.voices:
        file.write(
            _mastered(
                mixer.render(BLOCK_SIZE, np.float32, channels), player.output_gain
            )
        )


def _channels(data: np.ndarray, channels: int) -> np.ndarray:
    if data.shape[1] == channels:
        return data
    if channels == 1:
        return data.mean(axis=1)[:, np.newaxis]
    return np.repeat(data[:, :1], channels, axis=1)


def _mastered(block: np.ndarray, master_gain: float) -> np.ndarray:
    block *= master_gain
    return block


def _set_comment(
    file: soundfile.SoundFile,
    app: App,
    preset_names: Sequence[str],
    start_time: datetime,
) -> None:
    import soundfile

    try:
        file.comment = tomlkit.dumps(
            {
                'original_text': app.display_text,
                'presets': list(preset_names),
                'recording_start_time': start_time.isoformat(),
                'recording_finish_time': datetime.now(timezone.utc).isoformat(),
                'settings': tomlkit.dumps(serialize(app.dump_data())),
            }
        )
    except soundfile.LibsndfileError as error:
        if 'File type does not support string data' not in str(error):
            raise
