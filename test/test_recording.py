from pathlib import Path
from threading import Event, Thread, get_ident

import numpy as np
import pytest
import soundfile

from tuney.audio.engine import AudioEngine
from tuney.audio.mixer import Mixer, NotePress
from tuney.audio.output_file import AudioFileWriter
from tuney.audio.recording import Recording
from tuney.audio.voice import Voice


def test_recording_copies_samples_and_stop_waits_for_writer(
    tmp_path: Path, file_regression
) -> None:
    entered, release, stopped = Event(), Event(), Event()
    path = tmp_path / 'recording.wav'

    class Writer(AudioFileWriter):
        def write(self, block: np.ndarray) -> None:
            entered.set()
            assert release.wait(5)
            super().write(block)

    recording = Recording(Writer(path, 48_000, 1))
    block = np.full((48_000, 1), 0.25)
    recording.write(block)
    try:
        assert entered.wait(5)
        block[:] = 0.5

        def stop() -> None:
            recording.close()
            stopped.set()

        thread = Thread(target=stop)
        thread.start()
        assert not stopped.wait(0.05)
    finally:
        release.set()
        recording.close()
    thread.join(5)
    assert stopped.is_set()
    recording.write(block)
    audio, rate = soundfile.read(path)
    assert rate == 48_000
    np.testing.assert_array_equal(audio, np.full(48_000, 0.25))
    file_regression.check(path.read_bytes(), binary=True, extension='.wav')


def test_recording_overload_reports_failure_without_blocking(tmp_path: Path) -> None:
    entered, release = Event(), Event()

    class Writer(AudioFileWriter):
        def write(self, block: np.ndarray) -> None:
            entered.set()
            assert release.wait(5)
            super().write(block)

    recording = Recording(Writer(tmp_path / 'overload.wav', 48_000, 1), capacity=1)
    block = np.zeros((48_000, 1))
    recording.write(block)
    try:
        assert entered.wait(5)
        recording.write(block)
        recording.write(block)
    finally:
        release.set()
    with pytest.raises(RuntimeError, match='cannot keep up'):
        recording.close()
    assert recording.writer.file.closed
    engine = AudioEngine(mixer=Mixer(voice_maker=lambda _: Voice()), recorder=recording)
    engine.process_notifications()
    assert engine.diagnostics.take_errors() == [
        'Recording failed: Recording stopped: disk writer cannot keep up'
    ]
    engine.process_notifications()
    assert engine.diagnostics.take_errors() == []


def test_recording_write_failure_reaches_caller(tmp_path: Path) -> None:
    class Writer(AudioFileWriter):
        def write(self, block: np.ndarray) -> None:
            raise OSError('disk full')

    recording = Recording(Writer(tmp_path / 'failure.wav', 48_000, 1))
    recording.write(np.zeros((48_000, 1)))
    with pytest.raises(OSError, match='disk full'):
        recording.close()
    assert recording.writer.file.closed


def test_voice_preparation_runs_on_submitting_thread(
    tmp_path: Path, file_regression
) -> None:
    threads: list[int] = []

    def make_voice(note: int) -> Voice:
        threads.append(get_ident())
        return Voice(frequency=440)

    engine = AudioEngine(mixer=Mixer(voice_maker=make_voice))
    engine.submit(NotePress(0))
    block = np.zeros((48_000, 1))
    thread = Thread(target=engine.callback, args=(block, len(block), None, None))
    thread.start()
    thread.join(5)
    assert not thread.is_alive()
    assert threads == [get_ident()]
    path = tmp_path / 'voice.wav'
    soundfile.write(path, block, 48_000, subtype='PCM_16')
    expected = Mixer(voice_maker=lambda _: Voice(frequency=440))
    expected.apply(NotePress(0))
    np.testing.assert_allclose(
        soundfile.read(path)[0], expected.render(48_000)[:, 0], atol=1 / 32768
    )
    file_regression.check(path.read_bytes(), binary=True, extension='.wav')
