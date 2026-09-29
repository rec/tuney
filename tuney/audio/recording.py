from queue import Empty, Full, Queue
from threading import Event, Lock, Thread

import numpy as np

from .output_file import AudioFileWriter

RECORDING_CLOSE_TIMEOUT_SECONDS = 5.0


class Recording:
    """Queue owned sample copies; only the worker writes to the file."""

    def __init__(self, writer: AudioFileWriter, capacity: int = 4096) -> None:
        self.writer = writer
        self.blocks: Queue[np.ndarray] = Queue(capacity)
        self.lock = Lock()
        self.stopping = Event()
        self.accepting = True
        self.error: OSError | RuntimeError | ValueError | None = None
        self.error_reported = False
        self.worker = Thread(target=self._write, name='tuney-recording', daemon=True)
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
        self.stopping.set()
        self.worker.join(RECORDING_CLOSE_TIMEOUT_SECONDS)
        if self.worker.is_alive():
            self.error = TimeoutError(
                'Recording writer did not stop within '
                f'{RECORDING_CLOSE_TIMEOUT_SECONDS:g} seconds; '
                'recording may be incomplete'
            )
            raise self.error
        if self.error is not None:
            raise self.error

    def _write(self) -> None:
        try:
            while True:
                try:
                    block = self.blocks.get(timeout=0.1)
                except Empty:
                    if self.stopping.is_set():
                        break
                    continue
                if self.error is None:
                    try:
                        self.writer.write(block)
                    except (OSError, RuntimeError, ValueError) as error:
                        self.error = error
        finally:
            try:
                self.writer.close()
            except (OSError, RuntimeError, ValueError) as error:
                if self.error is None:
                    self.error = error
