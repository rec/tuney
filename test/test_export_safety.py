from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile

from tuney.app.app import App
from tuney.app.audio_recorder import AudioRecorder
from tuney.app.file_output import atomic_output
from tuney.audio.mixer import NotePress
from tuney.audio.player import Player


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('partial', [False, True])
def test_failed_offline_export_preserves_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, existing: bool, partial: bool
) -> None:
    destination = tmp_path / 'performance.wav'
    original = b''
    if existing:
        soundfile.write(destination, np.zeros(48_000), 48_000)
        original = destination.read_bytes()

    def fail(
        self: Player,
        output: Path,
        events: list[tuple[int, NotePress]],
        comment: Callable[[], str] | None,
    ) -> None:
        if partial:
            soundfile.write(output, np.ones(48_000), 48_000)
        raise RuntimeError('export failed')

    monkeypatch.setattr(Player, 'render_file', fail)
    with pytest.raises(RuntimeError, match='export failed'):
        App(output=destination, silent=True, text='a').run_cli()

    assert destination.exists() == existing
    if existing:
        assert destination.read_bytes() == original
    assert list(tmp_path.iterdir()) == ([destination] if existing else [])


@pytest.mark.parametrize('stage', ['start_recording', 'play_cli', 'stop_recording'])
def test_failed_live_export_preserves_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str
) -> None:
    destination = tmp_path / 'performance.wav'
    soundfile.write(destination, np.zeros(48_000), 48_000)
    original = destination.read_bytes()
    closed: list[bool] = []

    def fail(*args: object) -> None:
        raise RuntimeError('export failed')

    monkeypatch.setattr(Player, 'start_recording', lambda *a: None)
    monkeypatch.setattr(Player, 'stop_recording', lambda *a: None)
    monkeypatch.setattr(Player, 'stop_all', lambda *a: None)
    monkeypatch.setattr(Player, 'wait', lambda *a: None)
    monkeypatch.setattr(Player, 'close', lambda *a: closed.append(True))
    monkeypatch.setattr(App, 'play_cli', lambda *a: None)
    monkeypatch.setattr(App if stage == 'play_cli' else Player, stage, fail)

    with pytest.raises(RuntimeError, match='export failed'):
        App(output=destination, text='a').run_cli()

    assert destination.read_bytes() == original
    assert list(tmp_path.iterdir()) == [destination]
    assert closed == [True]


def test_atomic_output_replaces_only_after_success(tmp_path: Path) -> None:
    destination = tmp_path / 'output.txt'
    destination.write_text('original')
    with atomic_output(destination) as output:
        output.write_text('replacement')
        assert destination.read_text() == 'original'
    assert destination.read_text() == 'replacement'
    assert list(tmp_path.iterdir()) == [destination]


def test_failed_replace_preserves_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / 'output.txt'
    destination.write_text('original')

    def fail(self: Path, target: Path) -> Path:
        raise OSError('replace failed')

    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(OSError, match='replace failed'):
        with atomic_output(destination) as output:
            output.write_text('replacement')
    assert destination.read_text() == 'original'
    assert list(tmp_path.iterdir()) == [destination]


def test_failed_recording_save_preserves_recording_and_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / 'recording.wav'
    destination = tmp_path / 'saved.wav'
    soundfile.write(source, np.ones(48_000), 48_000)
    soundfile.write(destination, np.zeros(48_000), 48_000)
    original = destination.read_bytes()
    recording = source.read_bytes()
    recorder = AudioRecorder(path=source, started=True)

    def fail(source: Path, output: Path) -> None:
        soundfile.write(output, np.ones(48_000), 48_000)
        raise OSError('copy failed')

    monkeypatch.setattr('tuney.app.audio_recorder.copyfile', fail)
    with pytest.raises(OSError, match='copy failed'):
        recorder.save(destination)

    assert destination.read_bytes() == original
    assert source.read_bytes() == recording
    assert recorder.path == source
    assert sorted(tmp_path.iterdir()) == sorted([source, destination])
