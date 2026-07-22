from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .mixer import Mixer, NotePress

if TYPE_CHECKING:
    import soundfile

BLOCK_SIZE = 1024


class AudioFileWriter:
    def __init__(
        self,
        path: Path,
        sample_rate: int,
        channels: int,
        comment: Callable[[], str] | None = None,
        append: bool = False,
    ) -> None:
        import soundfile

        if append:
            self.file = soundfile.SoundFile(path, mode='r+')
            self.file.seek(0, soundfile.SEEK_END)
        else:
            self.file = soundfile.SoundFile(
                path,
                mode='w',
                samplerate=sample_rate,
                channels=channels,
            )
        self.comment = comment
        if self.comment is not None:
            self._set_comment(self.comment())

    def write(self, block: np.ndarray) -> None:
        self.file.write(block)

    def close(self) -> None:
        if self.comment is not None:
            self._set_comment(self.comment())
        self.file.close()

    def _set_comment(self, comment: str) -> None:
        _set_comment(self.file, comment)


def render_file(
    path: Path,
    mixer: Mixer,
    events: list[tuple[int, NotePress]],
    sample_rate: int,
    channels: int,
    comment: Callable[[], str] | None = None,
    master_gain: float = 1.0,
) -> None:
    import soundfile

    rendered = 0
    with soundfile.SoundFile(
        path,
        mode='w',
        samplerate=sample_rate,
        channels=channels,
    ) as file:
        if comment is not None:
            _set_comment(file, comment())

        for frame, note in events:
            if frame > rendered:
                file.write(
                    _mastered(
                        mixer.render(frame - rendered, np.float32, channels),
                        master_gain,
                    )
                )
                rendered = frame
            mixer.apply(note)

        mixer.stop_all()
        while mixer.voices:
            file.write(
                _mastered(mixer.render(BLOCK_SIZE, np.float32, channels), master_gain)
            )

        if comment is not None:
            _set_comment(file, comment())


def _set_comment(file: 'soundfile.SoundFile', comment: str) -> None:
    import soundfile

    try:
        file.comment = comment
    except soundfile.LibsndfileError as error:
        if 'File type does not support string data' not in str(error):
            raise


def _mastered(block: np.ndarray, master_gain: float) -> np.ndarray:
    block *= master_gain
    return block
