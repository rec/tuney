import json
import subprocess
from collections.abc import Callable

import mido
import numpy as np
import pytest

from tuney.audio import device
from tuney.audio.device import Device
from tuney.audio.oscillator import Oscillator, Waveform
from tuney.audio.sample_data import SampleData
from tuney.audio.sound import Binaural, Sound
from tuney.midi import port, ports, tuning_dump
from tuney.midi.midi import Midi, MidiIn, MidiOut
from tuney.scale.scale import Scale
from tuney.scale.tuning import Tuning
from tuney.ui.layout import Layout


@pytest.fixture(autouse=True)
def clear_midi_name_caches() -> None:
    ports.midi_names.cache_clear()


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
        device.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'headphones', 'max_output_channels': 2},
        ],
    )
    device.device_names.cache_clear()

    assert device.device_names() == ['speaker', 'headphones']


def test_output_device_names_include_index_when_names_are_duplicated(monkeypatch):
    monkeypatch.setattr(
        device.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'headphones', 'max_output_channels': 2},
        ],
    )
    device.device_names.cache_clear()

    assert device.device_names() == [
        '[0] speaker',
        '[2] speaker',
        'headphones',
    ]


def test_output_device_label_with_index_is_stored_as_index() -> None:
    assert Device(device='[7] Speakers (Realtek(R) Audio)').device == 7


def test_output_device_resolves_duplicate_name_to_index(monkeypatch) -> None:
    monkeypatch.setattr(
        device.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'mic', 'max_output_channels': 0},
            {'name': 'speaker', 'max_output_channels': 2},
        ],
    )

    assert device.output_device('speaker') == 0


def test_refresh_devices_clears_cached_device_names(monkeypatch) -> None:
    devices = [[{'name': 'first', 'max_output_channels': 2}]]
    monkeypatch.setattr(
        device.sounddevice,
        'query_devices',
        lambda: devices[-1],
    )
    midi_ports = [[['first input'], ['first output']]]

    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process(f'{midi_ports[-1]!r}'.replace("'", '"'))

    monkeypatch.setattr(
        ports.subprocess,
        'run',
        run,
    )
    device.device_names.cache_clear()

    class OptionControl:
        names: list[str] = []

        def refresh(self) -> None:
            self.names = device.device_names() + ports.midi_names()[1]

    option = OptionControl()
    layout = type(
        'FakeLayout',
        (),
        {'control_panel': type('Panel', (), {'option_controls': [option]})()},
    )()
    assert device.device_names() == ['first']
    assert ports.midi_names() == [['first input'], ['first output']]
    devices.append([{'name': 'second', 'max_output_channels': 2}])
    midi_ports.append([['second input'], ['second output']])

    Layout.refresh_devices(layout)

    assert option.names == ['second', 'second output']


def test_midi_names_uses_subprocess(monkeypatch):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process('[["keyboard", "controller"], ["synth"]]')

    monkeypatch.setattr(ports.subprocess, 'run', run)

    assert ports.midi_names() == [['keyboard', 'controller'], ['synth']]


def test_midi_names_cache_can_be_replaced_without_subprocess(monkeypatch) -> None:
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError('subprocess should not run')

    monkeypatch.setattr(ports.subprocess, 'run', run)
    ports.midi_names.replace([['keyboard'], ['synth']])

    assert ports.midi_names() == [['keyboard'], ['synth']]


def test_midi_names_uses_internal_subprocess_when_frozen(monkeypatch):
    calls: list[list[str]] = []

    def run(args: list[str], **__: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return completed_process('[["keyboard"], ["synth"]]', args=args)

    monkeypatch.setattr(ports.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(ports.sys, 'executable', 'Tuney')
    monkeypatch.setattr(ports.subprocess, 'run', run)

    assert ports.midi_names() == [['keyboard'], ['synth']]
    assert calls == [['Tuney', ports.LIST_MIDI]]


def test_midi_names_json_handles_output_probe_failure(monkeypatch, capsys):
    def get_output_names() -> list[str]:
        raise RuntimeError('MIDI unavailable')

    monkeypatch.setattr(ports.mido, 'get_input_names', lambda: ['keyboard'])
    monkeypatch.setattr(ports.mido, 'get_output_names', get_output_names)

    assert ports.midi_names_json() == json.dumps([['keyboard'], []], indent=2)
    assert 'Could not list MIDI outputs: MIDI unavailable' in capsys.readouterr().err


def test_midi_names_json_handles_input_probe_failure(monkeypatch, capsys):
    def get_input_names() -> list[str]:
        raise RuntimeError('MIDI unavailable')

    monkeypatch.setattr(ports.mido, 'get_input_names', get_input_names)
    monkeypatch.setattr(ports.mido, 'get_output_names', lambda: ['synth'])

    assert ports.midi_names_json() == json.dumps([[], ['synth']], indent=2)
    assert 'Could not list MIDI inputs: MIDI unavailable' in capsys.readouterr().err


def test_midi_names_returns_empty_lists_on_probe_failure(monkeypatch, capsys):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, [])

    monkeypatch.setattr(ports.subprocess, 'run', run)

    assert ports.midi_names() == [[], []]
    assert 'Could not list MIDI ports:' in capsys.readouterr().err


def test_midi_names_returns_empty_lists_for_bad_output(monkeypatch, capsys):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process('{}')

    monkeypatch.setattr(ports.subprocess, 'run', run)

    assert ports.midi_names() == [[], []]
    assert (
        'Could not list MIDI ports: expected two lists, got dict'
        in capsys.readouterr().err
    )


def test_midi_names_returns_empty_lists_for_wrong_list_shape(monkeypatch, capsys):
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return completed_process('["keyboard"]')

    monkeypatch.setattr(ports.subprocess, 'run', run)

    assert ports.midi_names() == [[], []]
    assert (
        'Could not list MIDI ports: expected two lists, got list'
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
    midi = MidiIn(channel=raw)

    assert midi.channel == channel
    assert midi.mido_channel == mido_channel


@pytest.mark.parametrize(
    'raw', [False, True, -1, 17, 'channel_1', '17', 'bad', 1.5, [], object()]
)
def test_midi_channel_rejects_invalid_values(raw: object) -> None:
    with pytest.raises(ValueError, match='MIDI channel must be omni'):
        MidiIn(channel=raw)
    with pytest.raises(ValueError, match='MIDI channel must be omni'):
        MidiOut(channel=raw)


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
    midi = MidiOut(channel=raw)

    assert midi.channel == channel
    assert midi.mido_channel == mido_channel


@pytest.mark.parametrize(('channel', 'expected'), [(3, 2), ('omni', 0)])
def test_midi_output_start_sends_program_and_volume_on_mido_channel(
    channel: int | str, expected: int, monkeypatch
) -> None:
    messages = []

    class Port:
        def send(self, message: object) -> None:
            messages.append(message)

    monkeypatch.setattr(port.mido, 'open_output', lambda *_args, **_kwargs: Port())

    MidiOut(enable=True, channel=channel, program=40).start()

    assert [(m.type, m.channel) for m in messages] == [
        ('program_change', expected),
        ('control_change', expected),
    ]
    assert messages[0].program == 40
    assert messages[1].control == 7
    assert messages[1].value == 100


def test_midi_output_skips_program_change_when_program_is_none(monkeypatch) -> None:
    messages = []

    class Port:
        def send(self, message: object) -> None:
            messages.append(message)

    monkeypatch.setattr(port.mido, 'open_output', lambda *_args, **_kwargs: Port())

    MidiOut(enable=True, program=None).start()

    assert [m.type for m in messages] == ['control_change']


def test_midi_output_sends_note_without_startup_messages(monkeypatch) -> None:
    messages = []

    class Port:
        def send(self, message: object) -> None:
            messages.append(message)

    monkeypatch.setattr(port.mido, 'open_output', lambda *_args, **_kwargs: Port())

    MidiOut(enable=True, program=40).send_note(60, True)

    assert [m.type for m in messages] == ['note_on']


def test_midi_output_tuning_dump_uses_midi_tuning_standard() -> None:
    message = tuning_dump.tuning_dump(Scale(), Tuning())

    assert message.type == 'sysex'
    assert message.data[:5] == (0x7E, 0x7F, 0x08, 0x01, 0)
    assert bytes(message.data[5:21]).decode('ascii') == 'Tuney           '
    assert len(message.data) == 406
    assert message.data[21 : 21 + 6] == (0, 0, 0, 1, 0, 0)
    assert message.data[21 + 69 * 3 : 21 + 70 * 3] == (69, 0, 0)
    assert message.data[-1] == tuning_dump._tuning_checksum(list(message.data[:-1]))


def test_midi_input_listener_converts_note_without_sending_output() -> None:
    events = []
    midi = Midi(
        input=MidiIn(enable=True, channel=3),
        output=MidiOut(note_offset=12),
    )
    listener = midi.listener(lambda note, is_press: events.append((note, is_press)))

    listener.on_message(mido.Message('note_on', channel=2, note=72, velocity=64))
    listener.on_message(mido.Message('note_on', channel=3, note=72, velocity=64))
    listener.on_message(mido.Message('note_off', channel=2, note=72, velocity=0))

    assert events == [(60, True), (60, False)]


def test_midi_input_listener_opens_selected_input(monkeypatch) -> None:
    opened = []

    class Port:
        def close(self) -> None:
            pass

    def open_input(
        port: str | None,
        *,
        callback: Callable[[mido.Message], None],
        virtual: bool,
    ) -> Port:
        opened.append((port, virtual, callback))
        return Port()

    midi = Midi(input=MidiIn(enable=True, name='keyboard'))
    listener = midi.listener(lambda note, is_press: None)
    monkeypatch.setattr(port.mido, 'open_input', open_input)

    listener.start()

    assert opened == [('keyboard', False, listener.on_message)]


@pytest.mark.parametrize('platform', ['darwin', 'linux'])
def test_midi_output_creates_virtual_port_by_default(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    opened = []

    class Port:
        def send(self, message: object) -> None:
            pass

    def open_output(port: str | None, *, virtual: bool) -> Port:
        opened.append((port, virtual))
        return Port()

    monkeypatch.setattr(port, 'VIRTUAL_ENABLED', platform in {'darwin', 'linux'})
    monkeypatch.setattr(port.mido, 'open_output', open_output)

    MidiOut(enable=True).start()

    assert opened == [('Tuney MIDI Out', True)]


@pytest.mark.parametrize('platform', ['darwin', 'linux'])
def test_midi_input_creates_virtual_port_by_default(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    opened = []

    class Port:
        def close(self) -> None:
            pass

    def open_input(
        port: str | None,
        *,
        callback: Callable[[mido.Message], None],
        virtual: bool,
    ) -> Port:
        opened.append((port, virtual, callback))
        return Port()

    midi = Midi(input=MidiIn(enable=True))
    listener = midi.listener(lambda note, is_press: None)
    monkeypatch.setattr(port, 'VIRTUAL_ENABLED', platform in {'darwin', 'linux'})
    monkeypatch.setattr(port.mido, 'open_input', open_input)

    listener.start()

    assert opened == [('Tuney MIDI In', True, listener.on_message)]


def test_midi_output_uses_selected_port_instead_of_virtual_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = []

    class Port:
        def send(self, message: object) -> None:
            pass

    def open_output(port: str | None, *, virtual: bool) -> Port:
        opened.append((port, virtual))
        return Port()

    monkeypatch.setattr(port, 'VIRTUAL_ENABLED', True)
    monkeypatch.setattr(port.mido, 'open_output', open_output)

    MidiOut(enable=True, name='External Synth').start()

    assert opened == [('External Synth', False)]


def test_midi_output_open_failure_disables_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def open_output(*_: object, **__: object) -> object:
        raise SystemError('MidiOutWinMM::openPort: error creating port')

    midi = MidiOut(enable=True)
    monkeypatch.setattr(port.mido, 'open_output', open_output)

    midi.start()
    midi.send_tuning_dump(Scale(), Tuning())
    midi.send_note(60, True)

    assert not midi.enable
    assert midi.pop_open_error() == 'MidiOutWinMM::openPort: error creating port'
    assert (
        'Could not open MIDI output: MidiOutWinMM::openPort' in capsys.readouterr().err
    )


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
