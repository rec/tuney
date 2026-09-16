from pathlib import Path

import numpy as np
import soundfile
from numpy.typing import DTypeLike

from tuney.audio.mixer import Mixer, NotePress
from tuney.audio.output_file import BLOCK_SIZE, render_file
from tuney.audio.voice import Voice


def test_export_bounds_blocks_and_preserves_event_frames(
    tmp_path: Path, file_regression
) -> None:
    class BoundedMixer(Mixer):
        def render(
            self, frame_size: int, dtype: DTypeLike = float, channels: int | None = None
        ) -> np.ndarray:
            assert frame_size <= BLOCK_SIZE
            return super().render(frame_size, dtype, channels)

    mixer = BoundedMixer(
        voice_maker=lambda _: Voice(
            frequency=440, fade_in=0, fade_out=0, minimum_note_time=0
        )
    )
    path = tmp_path / 'gaps.wav'
    render_file(
        path,
        mixer,
        [
            (137, NotePress(0)),
            (48_139, NotePress(0, False)),
            (96_157, NotePress(0)),
            (144_211, NotePress(0, False)),
        ],
        48_000,
        1,
    )
    audio, rate = soundfile.read(path)
    assert rate == 48_000
    assert len(audio) == 144_211
    assert not audio[:137].any()
    assert audio[138] != 0
    assert not audio[48_139:96_157].any()
    assert audio[96_158] != 0
    file_regression.check(path.read_bytes(), binary=True, extension='.wav')
