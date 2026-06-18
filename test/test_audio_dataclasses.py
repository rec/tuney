import subprocess
from typing import Any

import numpy as np
from pydantic import PrivateAttr

from tuney.audio import device as device_module
from tuney.audio import midi as midi_module
from tuney.audio.oscillator import Oscillator, Waveform
from tuney.audio.player import Player
from tuney.audio.sample_data import SampleData


class _Stream:
    def __enter__(self) -> None:
        pass

    def __exit__(self, *_) -> None:
        pass


class _StopRecordingPlayer(Player):
    _did_stop: bool = PrivateAttr(False)

    @property
    def stream(self) -> _Stream:
        return _Stream()

    def _fill(self, out: np.ndarray) -> bool | None:
        return True

    def stop(self) -> None:
        self._did_stop = True
        super().stop()


def test_sample_data_reports_channels_and_cuts_from_center():
    data = np.arange(8).reshape((4, 2))
    sample_data = SampleData(data=data, samplerate=2)

    device = sample_data.device('speaker')
    cut = sample_data.cut_to(1)

    assert sample_data.channels == 2
    assert device.channels == 2
    assert device.device == 'speaker'
    assert device.samplerate == 2
    np.testing.assert_array_equal(cut.data, data[1:3])


def test_output_device_names_lists_unique_output_devices(monkeypatch):
    monkeypatch.setattr(
        device_module.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'headphones', 'max_output_channels': 2},
        ],
    )

    assert device_module.device_names() == ['speaker', 'headphones']


def test_midi_output_names_uses_subprocess(monkeypatch):
    def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='["synth", "keyboard"]',
            stderr='',
        )

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == ['synth', 'keyboard']


def test_midi_output_names_returns_empty_list_on_probe_failure(monkeypatch, capsys):
    def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, [])

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == []
    assert 'Could not list MIDI outputs:' in capsys.readouterr().out


def test_midi_output_names_returns_empty_list_for_bad_output(monkeypatch, capsys):
    def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{}',
            stderr='',
        )

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == []
    assert (
        'Could not list MIDI outputs: expected list, got dict'
        in capsys.readouterr().out
    )


def test_player_run_calls_stop_after_stoppable_signal():
    player = _StopRecordingPlayer()

    player.stoppable.stop()
    player.run()

    assert player._did_stop


def test_oscillator_default_period_matches_previous_phase_scaling():
    actual = Oscillator(waveform=Waveform.sine)(start=0, length=8, period=8)
    expected = np.sin(np.linspace(0, 2 * np.pi, 8, endpoint=False))

    np.testing.assert_allclose(actual, expected)
