import subprocess
from typing import Any

import numpy as np
import pytest

from tuney.audio import device as device_module
from tuney.audio import midi as midi_module
from tuney.audio.oscillator import Oscillator, Waveform
from tuney.audio.sample_data import SampleData
from tuney.audio.sound import Sound


def test_sample_data_reports_channels_and_cuts_from_center():
    data = np.arange(8).reshape((4, 2))
    sample_data = SampleData(data=data, sample_rate=2)

    device = sample_data.device('speaker')
    cut = sample_data.cut_to(1)

    assert sample_data.channels == 2
    assert device.channels == 2
    assert device.device == 'speaker'
    assert device.sample_rate == 2
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
        return completed_process('["synth", "keyboard"]')

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == ['synth', 'keyboard']


def test_midi_output_names_uses_internal_subprocess_when_frozen(monkeypatch):
    calls: list[list[str]] = []

    def run(args: list[str], **__: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return completed_process('["synth"]', args=args)

    monkeypatch.setattr(midi_module.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(midi_module.sys, 'executable', 'Tuney')
    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == ['synth']
    assert calls == [['Tuney', midi_module.INTERNAL_LIST_MIDI_OUTPUTS]]


def test_midi_output_names_handles_frozen_probe_failure(monkeypatch, capsys):
    def get_output_names() -> list[str]:
        raise RuntimeError('MIDI unavailable')

    monkeypatch.setattr(midi_module.mido, 'get_output_names', get_output_names)

    assert midi_module._output_names() == []
    assert 'Could not list MIDI outputs: MIDI unavailable' in capsys.readouterr().out


def test_midi_output_names_returns_empty_list_on_probe_failure(monkeypatch, capsys):
    def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, [])

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == []
    assert 'Could not list MIDI outputs:' in capsys.readouterr().out


def test_midi_output_names_returns_empty_list_for_bad_output(monkeypatch, capsys):
    def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        return completed_process('{}')

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == []
    assert (
        'Could not list MIDI outputs: expected list, got dict'
        in capsys.readouterr().out
    )


def test_oscillator_default_period_matches_previous_phase_scaling():
    actual = Oscillator(waveform=Waveform.sine)(start=0, length=8, period=8)
    expected = np.sin(np.linspace(0, 2 * np.pi, 8, endpoint=False))

    np.testing.assert_allclose(actual, expected)


def test_oscillator_square_uses_duty_cycle() -> None:
    actual = Oscillator(waveform=Waveform.square, duty_cycle=0.25)(
        start=0, length=8, period=8
    )

    np.testing.assert_allclose(actual, [1, 1, -1, -1, -1, -1, -1, -1])


def test_oscillator_key_scale_changes_gain_by_octave() -> None:
    oscillator = Oscillator(key_scale_note=64, key_scale=6)

    assert oscillator.gain(64) == 1
    assert oscillator.gain(76) == pytest.approx(10 ** (6 / 20))
    assert oscillator.gain(52) == pytest.approx(10 ** (-6 / 20))


def test_sound_note_gain_combines_output_and_keyboard_gain() -> None:
    sound = Sound(gain=0.25, oscillator=Oscillator(key_scale_note=64, key_scale=6))

    assert sound.note_gain(76) == pytest.approx(0.25 * 10 ** (6 / 20))


def completed_process(
    stdout: str, args: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args or [],
        returncode=0,
        stdout=stdout,
        stderr='',
    )
