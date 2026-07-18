import subprocess
from typing import Any

import numpy as np
import pytest

from tuney.audio import device as device_module
from tuney.audio import midi as midi_module
from tuney.audio.device import Device
from tuney.audio.oscillator import Oscillator, Waveform
from tuney.audio.sample_data import SampleData
from tuney.audio.sound import Sound
from tuney.ui.layout import Layout


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
    device_module.device_names.cache_clear()

    assert device_module.device_names() == ['speaker', 'headphones']


def test_output_device_names_include_index_when_names_are_duplicated(monkeypatch):
    monkeypatch.setattr(
        device_module.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'headphones', 'max_output_channels': 2},
        ],
    )
    device_module.device_names.cache_clear()

    assert device_module.device_names() == ['[0] speaker', '[2] speaker', 'headphones']


def test_output_device_label_with_index_is_stored_as_index() -> None:
    assert Device(device='[7] Speakers (Realtek(R) Audio)').device == 7


def test_output_device_resolves_duplicate_name_to_index(monkeypatch) -> None:
    monkeypatch.setattr(
        device_module.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'speaker', 'max_output_channels': 2},
        ],
    )

    assert device_module.output_device('speaker') == 0


def test_refresh_devices_clears_cached_device_names(monkeypatch) -> None:
    devices = [[{'name': 'first', 'max_output_channels': 2}]]
    monkeypatch.setattr(device_module.sounddevice, 'query_devices', lambda: devices[-1])
    device_module.device_names.cache_clear()

    class OptionControl:
        names: list[str] = []

        def refresh(self) -> None:
            self.names = device_module.device_names()

    option = OptionControl()
    layout = type(
        'FakeLayout',
        (),
        {'control_panel': type('Panel', (), {'option_controls': [option]})()},
    )()
    assert device_module.device_names() == ['first']
    devices.append([{'name': 'second', 'max_output_channels': 2}])

    Layout.refresh_devices(layout)

    assert option.names == ['second']


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
    assert 'Could not list MIDI outputs: MIDI unavailable' in capsys.readouterr().err


def test_midi_output_names_returns_empty_list_on_probe_failure(monkeypatch, capsys):
    def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, [])

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == []
    assert 'Could not list MIDI outputs:' in capsys.readouterr().err


def test_midi_output_names_returns_empty_list_for_bad_output(monkeypatch, capsys):
    def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        return completed_process('{}')

    monkeypatch.setattr(midi_module.subprocess, 'run', run)

    assert midi_module.output_names() == []
    assert (
        'Could not list MIDI outputs: expected list, got dict'
        in capsys.readouterr().err
    )


@pytest.mark.parametrize(
    ('raw', 'channel', 'mido_channel'),
    [
        (None, 'omni', None),
        (0, 'omni', None),
        ('0', 'omni', None),
        ('omni', 'omni', None),
        (1, 1, 0),
        ('1', 1, 0),
        (16, 16, 15),
        ('16', 16, 15),
    ],
)
def test_midi_input_channel_accepts_omni_and_channel_numbers(
    raw: object, channel: object, mido_channel: int | None
) -> None:
    midi = midi_module.MIDIIn(channel=raw)

    assert midi.channel == channel
    assert midi.mido_channel == mido_channel


@pytest.mark.parametrize(
    'raw', [False, True, -1, 17, 'channel_1', '17', 'bad', 1.5, [], object()]
)
def test_midi_channel_rejects_invalid_values(raw: object) -> None:
    with pytest.raises(ValueError, match='MIDI channel must be omni'):
        midi_module.MIDIIn(channel=raw)
    with pytest.raises(ValueError, match='MIDI channel must be omni'):
        midi_module.MidiOut(channel=raw)


@pytest.mark.parametrize(
    ('raw', 'channel', 'mido_channel'),
    [
        (None, 'omni', None),
        (0, 'omni', None),
        ('0', 'omni', None),
        ('omni', 'omni', None),
        (1, 1, 0),
        ('1', 1, 0),
        (16, 16, 15),
        ('16', 16, 15),
    ],
)
def test_midi_output_channel_accepts_omni_and_channel_numbers(
    raw: object, channel: object, mido_channel: int | None
) -> None:
    midi = midi_module.MidiOut(channel=raw)

    assert midi.channel == channel
    assert midi.mido_channel == mido_channel


@pytest.mark.parametrize(('channel', 'expected'), [(3, 2), ('omni', 0)])
def test_midi_output_sends_on_mido_channel(
    channel: int | str, expected: int, monkeypatch
) -> None:
    messages = []

    class Port:
        def send(self, message: object) -> None:
            messages.append(message)

    monkeypatch.setattr(midi_module.mido, 'open_output', lambda _: Port())

    midi_module.MidiOut(enable=True, channel=channel)(60, True)

    assert [m.channel for m in messages] == [expected]


def test_midi_input_listener_converts_note_without_sending_output() -> None:
    events = []
    midi = midi_module.MIDI(
        input=midi_module.MIDIIn(enable=True, channel=3),
        output=midi_module.MidiOut(note_offset=12),
    )
    listener = midi.input_listener(
        lambda note, is_press: events.append((note, is_press))
    )

    listener.on_message(
        midi_module.mido.Message('note_on', channel=2, note=72, velocity=64)
    )
    listener.on_message(
        midi_module.mido.Message('note_on', channel=3, note=72, velocity=64)
    )
    listener.on_message(
        midi_module.mido.Message('note_off', channel=2, note=72, velocity=0)
    )

    assert events == [(60, True), (60, False)]


def test_oscillator_uses_one_cycle_per_note_period():
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


def test_sound_master_gain_defaults_to_one() -> None:
    assert Sound().master_gain == 1.0


def completed_process(
    stdout: str, args: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args or [],
        returncode=0,
        stdout=stdout,
        stderr='',
    )
