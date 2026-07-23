import subprocess
from collections.abc import Callable

import numpy as np
import pytest

import tuney.audio.device
import tuney.midi.midi
import tuney.midi.ports
from tuney.audio.device import Device
from tuney.audio.oscillator import Oscillator, Waveform
from tuney.audio.sample_data import SampleData
from tuney.audio.sound import Binaural, Sound
from tuney.scale.scale import Scale
from tuney.scale.tuning import Tuning
from tuney.ui.layout import Layout


@pytest.fixture(autouse=True)
def clear_midi_name_caches() -> None:
    tuney.midi.ports.input_names.cache_clear()
    tuney.midi.ports.output_names.cache_clear()


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
        tuney.audio.device.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'headphones', 'max_output_channels': 2},
        ],
    )
    tuney.audio.device.device_names.cache_clear()

    assert tuney.audio.device.device_names() == ['speaker', 'headphones']


def test_output_device_names_include_index_when_names_are_duplicated(monkeypatch):
    monkeypatch.setattr(
        tuney.audio.device.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'headphones', 'max_output_channels': 2},
        ],
    )
    tuney.audio.device.device_names.cache_clear()

    assert tuney.audio.device.device_names() == [
        '[0] speaker',
        '[2] speaker',
        'headphones',
    ]


def test_output_device_label_with_index_is_stored_as_index() -> None:
    assert Device(device='[7] Speakers (Realtek(R) Audio)').device == 7


def test_output_device_resolves_duplicate_name_to_index(monkeypatch) -> None:
    monkeypatch.setattr(
        tuney.audio.device.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'speaker', 'max_output_channels': 2},
        ],
    )

    assert tuney.audio.device.output_device('speaker') == 0


def test_refresh_devices_clears_cached_device_names(monkeypatch) -> None:
    devices = [[{'name': 'first', 'max_output_channels': 2}]]
    monkeypatch.setattr(
        tuney.audio.device.sounddevice,
        'query_devices',
        lambda: devices[-1],
    )
    midi_outputs = [['first output']]

    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process(f'{midi_outputs[-1]!r}'.replace("'", '"'))

    monkeypatch.setattr(
        tuney.midi.ports.subprocess,
        'run',
        run,
    )
    tuney.audio.device.device_names.cache_clear()

    class OptionControl:
        names: list[str] = []

        def refresh(self) -> None:
            self.names = (
                tuney.audio.device.device_names() + tuney.midi.ports.output_names()
            )

    option = OptionControl()
    layout = type(
        'FakeLayout',
        (),
        {'control_panel': type('Panel', (), {'option_controls': [option]})()},
    )()
    assert tuney.audio.device.device_names() == ['first']
    assert tuney.midi.ports.output_names() == ['first output']
    devices.append([{'name': 'second', 'max_output_channels': 2}])
    midi_outputs.append(['second output'])

    Layout.refresh_devices(layout)

    assert option.names == ['second', 'second output']


def test_midi_output_names_uses_subprocess(monkeypatch):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process('["synth", "keyboard"]')

    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.output_names() == ['synth', 'keyboard']


def test_midi_input_names_uses_subprocess(monkeypatch):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process('["keyboard", "controller"]')

    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.input_names() == ['keyboard', 'controller']


def test_midi_output_names_uses_internal_subprocess_when_frozen(monkeypatch):
    calls: list[list[str]] = []

    def run(args: list[str], **__: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return completed_process('["synth"]', args=args)

    monkeypatch.setattr(tuney.midi.ports.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(tuney.midi.ports.sys, 'executable', 'Tuney')
    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.output_names() == ['synth']
    assert calls == [['Tuney', tuney.midi.ports.INTERNAL_LIST_MIDI_OUTPUTS]]


def test_midi_input_names_uses_internal_subprocess_when_frozen(monkeypatch):
    calls: list[list[str]] = []

    def run(args: list[str], **__: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return completed_process('["keyboard"]', args=args)

    monkeypatch.setattr(tuney.midi.ports.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(tuney.midi.ports.sys, 'executable', 'Tuney')
    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.input_names() == ['keyboard']
    assert calls == [['Tuney', tuney.midi.ports.INTERNAL_LIST_MIDI_INPUTS]]


def test_midi_output_names_handles_frozen_probe_failure(monkeypatch, capsys):
    def get_output_names() -> list[str]:
        raise RuntimeError('MIDI unavailable')

    monkeypatch.setattr(tuney.midi.ports.mido, 'get_output_names', get_output_names)

    assert tuney.midi.ports.output_names_json() == '[]'
    assert 'Could not list MIDI outputs: MIDI unavailable' in capsys.readouterr().err


def test_midi_input_names_handles_frozen_probe_failure(monkeypatch, capsys):
    def get_input_names() -> list[str]:
        raise RuntimeError('MIDI unavailable')

    monkeypatch.setattr(tuney.midi.ports.mido, 'get_input_names', get_input_names)

    assert tuney.midi.ports.input_names_json() == '[]'
    assert 'Could not list MIDI inputs: MIDI unavailable' in capsys.readouterr().err


def test_midi_output_names_returns_empty_list_on_probe_failure(monkeypatch, capsys):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, [])

    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.output_names() == []
    assert 'Could not list MIDI outputs:' in capsys.readouterr().err


def test_midi_input_names_returns_empty_list_on_probe_failure(monkeypatch, capsys):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, [])

    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.input_names() == []
    assert 'Could not list MIDI inputs:' in capsys.readouterr().err


def test_midi_output_names_returns_empty_list_for_bad_output(monkeypatch, capsys):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process('{}')

    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.output_names() == []
    assert (
        'Could not list MIDI outputs: expected list, got dict'
        in capsys.readouterr().err
    )


def test_midi_input_names_returns_empty_list_for_bad_output(monkeypatch, capsys):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process('{}')

    monkeypatch.setattr(tuney.midi.ports.subprocess, 'run', run)

    assert tuney.midi.ports.input_names() == []
    assert (
        'Could not list MIDI inputs: expected list, got dict' in capsys.readouterr().err
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
    midi = tuney.midi.midi.MidiIn(channel=raw)

    assert midi.channel == channel
    assert midi.mido_channel == mido_channel


@pytest.mark.parametrize(
    'raw', [False, True, -1, 17, 'channel_1', '17', 'bad', 1.5, [], object()]
)
def test_midi_channel_rejects_invalid_values(raw: object) -> None:
    with pytest.raises(ValueError, match='MIDI channel must be omni'):
        tuney.midi.midi.MidiIn(channel=raw)
    with pytest.raises(ValueError, match='MIDI channel must be omni'):
        tuney.midi.midi.MidiOut(channel=raw)


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
    midi = tuney.midi.midi.MidiOut(channel=raw)

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

    monkeypatch.setattr(tuney.midi.midi.mido, 'open_output', lambda _: Port())

    tuney.midi.midi.MidiOut(enable=True, channel=channel, program=40)(60, True)

    assert [(m.type, m.channel) for m in messages] == [
        ('program_change', expected),
        ('control_change', expected),
        ('note_on', expected),
    ]
    assert messages[0].program == 40
    assert messages[1].control == 7
    assert messages[1].value == 100


def test_midi_output_skips_program_change_when_program_is_none(monkeypatch) -> None:
    messages = []

    class Port:
        def send(self, message: object) -> None:
            messages.append(message)

    monkeypatch.setattr(tuney.midi.midi.mido, 'open_output', lambda _: Port())

    tuney.midi.midi.MidiOut(enable=True, program=None)(60, True)

    assert [m.type for m in messages] == ['control_change', 'note_on']


def test_midi_output_tuning_dump_uses_midi_tuning_standard() -> None:
    midi = tuney.midi.midi.MidiOut(send_tuning=True)

    message = midi.tuning_dump(Scale(), Tuning())

    assert message.type == 'sysex'
    assert message.data[:5] == (0x7E, 0x7F, 0x08, 0x01, 0)
    assert bytes(message.data[5:21]).decode('ascii') == 'Tuney           '
    assert len(message.data) == 406
    assert message.data[21 : 21 + 6] == (0, 0, 0, 1, 0, 0)
    assert message.data[21 + 69 * 3 : 21 + 70 * 3] == (69, 0, 0)
    assert message.data[-1] == tuney.midi.midi._tuning_checksum(list(message.data[:-1]))


def test_midi_input_listener_converts_note_without_sending_output() -> None:
    events = []
    midi = tuney.midi.midi.Midi(
        input=tuney.midi.midi.MidiIn(enable=True, channel=3),
        output=tuney.midi.midi.MidiOut(note_offset=12),
    )
    listener = midi.listener(lambda note, is_press: events.append((note, is_press)))

    listener.on_message(
        tuney.midi.midi.mido.Message('note_on', channel=2, note=72, velocity=64)
    )
    listener.on_message(
        tuney.midi.midi.mido.Message('note_on', channel=3, note=72, velocity=64)
    )
    listener.on_message(
        tuney.midi.midi.mido.Message('note_off', channel=2, note=72, velocity=0)
    )

    assert events == [(60, True), (60, False)]


def test_midi_input_listener_opens_selected_input(monkeypatch) -> None:
    opened = []

    class Port:
        def close(self) -> None:
            pass

    def open_input(
        port: str | None, *, callback: Callable[[tuney.midi.midi.mido.Message], None]
    ) -> Port:
        opened.append((port, callback))
        return Port()

    midi = tuney.midi.midi.Midi(
        input=tuney.midi.midi.MidiIn(enable=True, name='keyboard')
    )
    listener = midi.listener(lambda note, is_press: None)
    monkeypatch.setattr(tuney.midi.midi.mido, 'open_input', open_input)

    listener.start()

    assert opened == [('keyboard', listener.on_message)]


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


def test_binaural_defaults_and_constraints() -> None:
    binaural = Binaural()

    assert not binaural.enable
    assert binaural.frequency == 7.8
    assert binaural.width == 1.0

    with pytest.raises(ValueError):
        Binaural(frequency=0)
    with pytest.raises(ValueError):
        Binaural(width=-1.01)
    with pytest.raises(ValueError):
        Binaural(width=1.01)


def completed_process(
    stdout: str, args: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args or [],
        returncode=0,
        stdout=stdout,
        stderr='',
    )
