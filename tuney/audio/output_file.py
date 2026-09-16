from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .mixer import Mixer, NotePress
from .speech import SpeechPlayback

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
        try:
            if self.comment is not None:
                self._set_comment(self.comment())
        finally:
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
    speech: SpeechPlayback | None = None,
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
            while frame > rendered:
                count = min(BLOCK_SIZE, frame - rendered)
                file.write(
                    _mastered(
                        mixer.render(count, np.float32, channels),
                        master_gain,
                        speech,
                    )
                )
                rendered += count
            mixer.apply(note)

        mixer.stop_all()
        while mixer.voices or (speech is not None and not speech.complete):
            count = BLOCK_SIZE
            if not mixer.voices and speech is not None:
                count = min(count, len(speech.data) - speech.position)
            file.write(
                _mastered(
                    mixer.render(count, np.float32, channels), master_gain, speech
                )
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


def _mastered(
    block: np.ndarray, master_gain: float, speech: SpeechPlayback | None
) -> np.ndarray:
    if speech is not None and not speech.complete:
        block += speech.render(len(block), block.dtype, block.shape[1])
    block *= master_gain
    return block
