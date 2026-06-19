from collections.abc import Callable
from pathlib import Path
from queue import SimpleQueue
from threading import Thread

import numpy as np
import soundfile

from .mixer import Mixer, NotePress

BLOCK_SIZE = 1024


class AudioFileWriter:
    def __init__(
        self,
        path: Path,
        sample_rate: int,
        channels: int,
        comment: Callable[[], str] | None = None,
    ) -> None:
        self.file = soundfile.SoundFile(
            path,
            mode='w',
            samplerate=sample_rate,
            channels=channels,
        )
        self.comment = comment
        if self.comment is not None:
            self._set_comment(self.comment())
        self.blocks = SimpleQueue[np.ndarray | None]()
        self.thread = Thread(target=self._write, daemon=True)
        self.thread.start()

    def write(self, block: np.ndarray) -> None:
        self.blocks.put(block.copy())

    def close(self) -> None:
        self.blocks.put(None)
        self.thread.join()
        if self.comment is not None:
            self._set_comment(self.comment())
        self.file.close()

    def _set_comment(self, comment: str) -> None:
        try:
            self.file.comment = comment
        except soundfile.LibsndfileError as error:
            if 'File type does not support string data' not in str(error):
                raise

    def _write(self) -> None:
        while (block := self.blocks.get()) is not None:
            self.file.write(block)


def render_file(
    path: Path,
    mixer: Mixer,
    events: list[tuple[int, NotePress]],
    sample_rate: int,
    channels: int,
    comment: Callable[[], str] | None = None,
) -> None:
    writer = AudioFileWriter(path, sample_rate, channels, comment)
    rendered = 0
    try:
        for frame, note in events:
            if frame > rendered:
                writer.write(mixer.render(frame - rendered, np.float32, channels))
                rendered = frame
            mixer.apply(note)

        mixer.stop_all()
        while mixer.voices:
            writer.write(mixer.render(BLOCK_SIZE, np.float32, channels))
    finally:
        writer.close()
