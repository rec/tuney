from io import BytesIO
from multiprocessing.process import BaseProcess
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest
import soundfile

from tuney.app.app import App
from tuney.app.export_job import ExportJob
from tuney.time.char_press import CharPress


def test_worker_exports_snapshot_and_reports_progress(
    tmp_path: Path, file_regression
) -> None:
    path = tmp_path / 'export.wav'
    app = App(text=[CharPress('a'), CharPress('a', False, 1100)])
    expected = tmp_path / 'expected.wav'
    app.player.render_file(expected, app.note_events(48_000))
    job = ExportJob(path, app)
    app.sound.master_gain = 0
    app.char_presses.clear()
    progress: list[int] = []
    deadline = monotonic() + 15
    try:
        while not job.poll():
            assert monotonic() < deadline
            progress.append(job.update.percent)
            sleep(0.01)
        assert job.update.error is None
        assert job.update.success
        assert progress
        assert job.update.percent == 100
        data, rate = soundfile.read(path)
        assert rate == 48_000
        assert len(data) >= 48_000
        np.testing.assert_array_equal(data, soundfile.read(expected)[0])
        wav = BytesIO()
        soundfile.write(wav, data, rate, format='WAV', subtype='PCM_16')
        file_regression.check(wav.getvalue(), binary=True, extension='.wav')
    finally:
        job.close()
    assert not job.temporary.exists()
    assert not Path(job.scratch.name).exists()


@pytest.mark.parametrize('existing', [False, True])
def test_cancelled_export_does_not_publish_or_leave_temporary_files(
    tmp_path: Path, existing: bool
) -> None:
    path = tmp_path / 'export.wav'
    if existing:
        path.write_bytes(b'previous recording')
    job = ExportJob(path, App(text=[CharPress('a'), CharPress('a', False, 600_000)]))
    (Path(job.scratch.name) / 'speech.wav').write_bytes(b'unfinished speech')
    deadline = monotonic() + 15
    try:
        while not job.receiver.poll():
            assert monotonic() < deadline
            sleep(0.01)
        job.cancel()
    finally:
        job.close()
    assert job.finished
    assert job.cancelled
    assert not Path(job.scratch.name).exists()
    assert path.exists() is existing
    if existing:
        assert path.read_bytes() == b'previous recording'
    assert list(tmp_path.iterdir()) == ([path] if existing else [])


def test_worker_failure_preserves_destination(tmp_path: Path) -> None:
    path = tmp_path / 'export.unsupported'
    path.write_bytes(b'original')
    job = ExportJob(path, App(text='a'))
    deadline = monotonic() + 15
    try:
        while not job.poll():
            assert monotonic() < deadline
            sleep(0.01)
        assert job.update.error
    finally:
        job.close()
    assert path.read_bytes() == b'original'
    assert list(tmp_path.iterdir()) == [path]


def test_process_start_failure_cleans_temporary_output(
    monkeypatch, tmp_path: Path
) -> None:
    def fail(self: BaseProcess) -> None:
        raise OSError('cannot start worker')

    monkeypatch.setattr(BaseProcess, 'start', fail)
    with pytest.raises(OSError, match='cannot start worker'):
        ExportJob(tmp_path / 'export.wav', App(text='a'))
    assert list(tmp_path.iterdir()) == []


def test_publish_failure_preserves_destination(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / 'export.wav'
    path.write_bytes(b'original')
    job = ExportJob(path, App(text=[CharPress('a'), CharPress('a', False, 1100)]))

    def fail(self: Path, target: Path) -> Path:
        raise OSError('cannot replace destination')

    monkeypatch.setattr(Path, 'replace', fail)
    deadline = monotonic() + 15
    try:
        while not job.poll():
            assert monotonic() < deadline
            sleep(0.01)
        assert job.update.error == 'cannot replace destination'
    finally:
        job.close()
    assert path.read_bytes() == b'original'
    assert list(tmp_path.iterdir()) == [path]
