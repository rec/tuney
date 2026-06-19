from pathlib import Path
from queue import SimpleQueue
from threading import Thread

import numpy as np
import soundfile

from .mixer import Mixer, NotePress

BLOCK_SIZE = 1024


class AudioFileWriter:
    def __init__(self, path: Path, sample_rate: int, channels: int) -> None:
        self.file = soundfile.SoundFile(
            path,
            mode='w',
            samplerate=sample_rate,
            channels=channels,
        )
        self.blocks = SimpleQueue[np.ndarray | None]()
        self.thread = Thread(target=self._write, daemon=True)
        self.thread.start()

    def write(self, block: np.ndarray) -> None:
        self.blocks.put(block.copy())

    def close(self) -> None:
        self.blocks.put(None)
        self.thread.join()
        self.file.close()

    def _write(self) -> None:
        while (block := self.blocks.get()) is not None:
            self.file.write(block)


def render_file(
    path: Path,
    mixer: Mixer,
    events: list[tuple[int, NotePress]],
    sample_rate: int,
    channels: int,
) -> None:
    writer = AudioFileWriter(path, sample_rate, channels)
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
