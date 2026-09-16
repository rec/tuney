from queue import Full, Queue
from threading import Lock, Thread

import numpy as np

from .output_file import AudioFileWriter


class Recording:
    """Queue owned sample copies; only the worker writes to the file."""

    def __init__(self, writer: AudioFileWriter, capacity: int = 4096) -> None:
        self.writer = writer
        self.blocks: Queue[np.ndarray | None] = Queue(capacity)
        self.lock = Lock()
        self.accepting = True
        self.error: OSError | RuntimeError | ValueError | None = None
        self.error_reported = False
        self.worker = Thread(target=self._write, name='tuney-recording')
        self.worker.start()

    def write(self, block: np.ndarray) -> None:
        with self.lock:
            if not self.accepting or self.error is not None:
                return
            try:
                self.blocks.put_nowait(block.copy())
            except Full:
                self.error = RuntimeError(
                    'Recording stopped: disk writer cannot keep up'
                )

    def close(self) -> None:
        with self.lock:
            if not self.accepting:
                return
            self.accepting = False
        self.blocks.put(None)
        self.worker.join()
        self.writer.close()
        if self.error is not None:
            raise self.error

    def _write(self) -> None:
        while (block := self.blocks.get()) is not None:
            if self.error is None:
                try:
                    self.writer.write(block)
                except (OSError, RuntimeError, ValueError) as error:
                    self.error = error
