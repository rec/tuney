import re
from pathlib import Path

import pytest
import tyro
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.__main__ import main
from tuney.cli import cli
from tuney.keyboard.char_press import CharPress
from tuney.tuney import Tuney

LONG_OPTION_RE = re.compile(r'(?<![\w-])--[a-z0-9][a-z0-9-]*')
SHORT_OPTION_RE = re.compile(r'(?<![\w-])-[^-\s]')
OPTIONS_WITHOUT_SHORT_ALIAS = {
    '--hover-time',
    '--backspace-repeat-delay',
    '--backspace-repeat-rate',
    '--polyphonic-headroom',
    '--max-polyphony',
    '--samplerate',
    '--dtype',
    '--table',
    '--table-blend',
    '--midi-enable',
    '--midi-output',
    '--midi-channel',
    '--midi-velocity',
    '--midi-note-offset',
    '--space',
    '--text-period',
    '--comma',
    '--colon',
    '--semicolon',
    '--blank-line',
    '--overlap',
    '--seed',
    '--alpha-only',
    '--strip-accents',
    '--text-scale',
    '--other',
    '--timings',
}
REMOVED_SHORT_ALIASES = {
    '-H',
    '-B',
    '-R',
    '-P',
    '-M',
    '-S',
    '-D',
    '-z',
    '-Z',
    '-0',
    '-1',
    '-2',
    '-3',
    '-4',
    '-5',
    '-6',
    '-7',
    '-8',
    '-9',
    '-@',
    '-_',
    '-?',
    '-+',
    '-%',
    '-:',
    '-.',
    '-,',
}


def test_tuney_help_output(
    capsys: pytest.CaptureFixture[str],
    file_regression: FileRegressionFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('COLUMNS', '120')
    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setattr('sys.argv', ['tuney', '--help'])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    file_regression.check(capsys.readouterr().out)


def test_cli_help_uses_flat_unique_names(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('COLUMNS', '120')
    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setattr('sys.argv', ['tuney', '--help'])

    with pytest.raises(SystemExit):
        main()

    help_text = capsys.readouterr().out
    long_options = [
        option for option in LONG_OPTION_RE.findall(help_text) if option != '--help'
    ]
    positive_long_options = [
        option for option in long_options if not option.startswith('--no-')
    ]

    assert all('.' not in option for option in long_options)
    assert len(positive_long_options) == len(set(positive_long_options))
    assert '--audio-device' in positive_long_options
    assert '--midi-output' in positive_long_options
    assert '--oscillator-period' in positive_long_options
    assert '--player.oscillator.period' not in help_text


def test_cli_help_gives_expected_public_options_a_short_alias(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('COLUMNS', '120')
    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setattr('sys.argv', ['tuney', '--help'])

    with pytest.raises(SystemExit):
        main()

    help_text = capsys.readouterr().out
    option_lines = [line.strip() for line in help_text.splitlines()]
    option_lines = [
        line
        for line in option_lines
        if line.startswith('-') and '--' in line and set(line) != {'-'}
    ]
    public_option_lines = [
        line for line in option_lines if not line.startswith('-h, --help')
    ]
    lines_with_short_alias = [
        line
        for line in public_option_lines
        if not any(option in line for option in OPTIONS_WITHOUT_SHORT_ALIAS)
    ]
    lines_without_short_alias = [
        line
        for line in public_option_lines
        if any(option in line for option in OPTIONS_WITHOUT_SHORT_ALIAS)
    ]
    short_options = [
        SHORT_OPTION_RE.search(line).group(0)
        for line in lines_with_short_alias
        if not re.search(r'--no-[a-z0-9-]+\b', line)
    ]

    assert len(short_options) == len(set(short_options))
    assert all(SHORT_OPTION_RE.search(line) for line in lines_with_short_alias)
    assert all(not SHORT_OPTION_RE.search(line) for line in lines_without_short_alias)
    assert all(line.startswith('--') for line in lines_without_short_alias)
    assert not any(alias in help_text for alias in REMOVED_SHORT_ALIASES)


def test_cli_accepts_flat_long_options() -> None:
    tuney = tyro.cli(
        Tuney,
        args=[
            '--mapper-alphabet=abc',
            '--audio-device=Built-in',
            '--oscillator-period=2',
            '--scale-alphabet=ABCDEFG',
            '--midi-output=Port',
            '--midi-channel=3',
            '--midi-velocity=80',
            '--midi-note-offset=12',
            '--text-period=301',
            '--text-scale=4',
            '--polyphonic-headroom=3',
            '--max-polyphony=8',
            '--samplerate=44100',
            '--dtype=int16',
            '--table',
            '440',
            '880',
            '--no-table-blend',
            '--space=101',
            '--comma=201',
            '--colon=401',
            '--semicolon=402',
            '--blank-line=1001',
            '--overlap=19',
            '--seed=42',
            '--alpha-only',
            '--strip-accents',
            '--other',
            '!',
            '500',
            '--timings',
            '10',
            '20',
        ],
    )

    assert tuney.mapper.alphabet == 'abc'
    assert tuney.player.device.device == 'Built-in'
    assert tuney.player.oscillator.period == 2
    assert tuney.player.scale.alphabet == 'ABCDEFG'
    assert tuney.midi.output == 'Port'
    assert tuney.midi.channel == 3
    assert tuney.midi.velocity == 80
    assert tuney.midi.note_offset == 12
    assert tuney.text_timings.period == 301
    assert tuney.text_timings.scale == 4
    assert tuney.player.polyphonic_headroom == 3
    assert tuney.player.max_polyphony == 8
    assert tuney.player.device.samplerate == 44100
    assert tuney.player.device.dtype.value == 'int16'
    assert tuney.player.scale.tuning.table == [440, 880]
    assert not tuney.player.scale.tuning.table_blend
    assert tuney.text_timings.space == 101
    assert tuney.text_timings.comma == 201
    assert tuney.text_timings.colon == 401
    assert tuney.text_timings.semicolon == 402
    assert tuney.text_timings.blank_line == 1001
    assert tuney.text_timings.overlap == 19
    assert tuney.text_timings.seed == 42
    assert tuney.text_timings.alpha_only
    assert tuney.text_timings.strip_accents
    assert tuney.text_timings.other == {'!': 500}
    assert tuney.text_timings.timings == [10, 20]


def test_cli_rejects_old_nested_options() -> None:
    with pytest.raises(SystemExit):
        tyro.cli(Tuney, args=['--player.oscillator.period=2'])


def test_cli_accepts_single_character_aliases() -> None:
    tuney = tyro.cli(
        Tuney,
        args=[
            '-p',
            'white-notes',
            '-c',
            'config.toml',
            '-t',
            'text',
            '-m',
            '3',
            '-g',
            '-s',
            '-o',
            'out.wav',
            '-b',
            '-a',
            'abc',
            '-l',
            '3',
            '-C',
            '-I',
            '-O',
            '1',
            '-r',
            '12',
            '-L',
            'reflect',
            '-G',
            '0.5',
            '-n',
            '47',
            '-N',
            '0.25',
            '-d',
            'Built-in',
            '-w',
            'sine',
            '-e',
            '2',
            '-u',
            '0.25',
            '-K',
            '60',
            '-k',
            '0.1',
            '-A',
            'ABCDEFG',
            '-q',
            'D',
            '-j',
            'A',
            '-E',
            'G',
            '-Q',
            'CDE',
            '-i',
            '2',
            '2',
            '1',
            '-X',
            'half',
            '-Y',
            '2',
            '-T',
            '5',
            '-v',
            '7',
            '-V',
            '19',
            '-J',
            '3',
            '-F',
            'linear',
            '-U',
            '442',
            '-W',
            '70',
        ],
    )

    assert tuney.preset == 'white-notes'
    assert tuney.config_file == Path('config.toml')
    assert tuney.text == 'text'
    assert tuney.max_gap == 3
    assert not tuney.gui
    assert tuney.silent
    assert tuney.output == Path('out.wav')
    assert tuney.run_in_background
    assert tuney.mapper.alphabet == 'abc'
    assert tuney.mapper.length == 3
    assert tuney.mapper.case_sensitive
    assert tuney.mapper.invert
    assert tuney.mapper.offset == 1
    assert tuney.mapper.range_limit == 12
    assert tuney.mapper.limiter.value == 'reflect'
    assert tuney.player.gain == 0.5
    assert tuney.player.note_offset == 47
    assert tuney.player.polyphonic_headroom == Tuney().player.polyphonic_headroom
    assert tuney.player.max_polyphony == Tuney().player.max_polyphony
    assert tuney.player.minimum_note_time == 0.25
    assert tuney.player.device.device == 'Built-in'
    assert tuney.player.oscillator.waveform.name == 'sine'
    assert tuney.player.oscillator.period == 2
    assert tuney.player.oscillator.duty_cycle == 0.25
    assert tuney.player.oscillator.key_scale_note == 60
    assert tuney.player.oscillator.key_scale == 0.1
    assert tuney.player.scale.alphabet == 'ABCDEFG'
    assert tuney.player.scale.root == 'D'
    assert tuney.player.scale.begin == 'A'
    assert tuney.player.scale.end == 'G'
    assert tuney.player.scale.notes == 'CDE'
    assert tuney.player.scale.intervals == [2, 2, 1]
    assert tuney.player.scale.accidentals.value == 'half'
    assert tuney.player.scale.offset == 2
    assert tuney.player.scale.tuning.detune == 5
    assert tuney.player.scale.tuning.limit == 7
    assert tuney.player.scale.tuning.notes_per_octave == 19
    assert tuney.player.scale.tuning.octave_ratio == 3
    assert tuney.player.scale.tuning.pitch_to_frequency.function.name == 'linear'
    assert tuney.player.scale.tuning.root_frequency == 442
    assert tuney.player.scale.tuning.root_note == 70


def test_removed_single_character_aliases_are_not_options() -> None:
    with pytest.raises(SystemExit):
        tyro.cli(Tuney, args=['-H', '0.5'])


def test_cli_accepts_text_option() -> None:
    tuney = tyro.cli(Tuney, args=['--text=Now is the time'])

    assert not tuney.gui
    assert tuney.text == 'Now is the time'


def test_cli_uses_positional_arguments_as_text() -> None:
    tuney = tyro.cli(Tuney, args=['Now', 'is', 'the', 'time'])

    assert tuney.text == 'Now is the time'


def test_cli_treats_positional_config_file_as_text() -> None:
    tuney = tyro.cli(Tuney, args=['config.toml'])

    assert tuney.config_file is None
    assert tuney.text == 'config.toml'


def test_cli_preserves_char_presses_from_config_default() -> None:
    text = [CharPress('a', time=0)]

    tuney = tyro.cli(Tuney, args=[], default=Tuney(text=text))

    assert tuney.text == text


def test_cli_positional_text_replaces_default_char_presses() -> None:
    default = Tuney(text=[CharPress('a', time=0), CharPress('a', False, 100)])

    tuney = tyro.cli(Tuney, args=['new', 'text'], default=default)

    assert tuney.text == 'new text'
    assert tuney.char_presses != default.char_presses


def test_output_option_forces_cli_mode() -> None:
    tuney = tyro.cli(Tuney, args=['--output=out.wav', '--text=a'])

    assert tuney.output == Path('out.wav')
    assert not tuney.gui


def test_gui_option_opens_gui_mode() -> None:
    tuney = tyro.cli(Tuney, args=['--gui'])

    assert tuney.gui


def test_cli_loads_preset_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[Tuney] = []

    def call(tuney: Tuney) -> None:
        captured.append(tuney)

    monkeypatch.setattr(Tuney, '__call__', call)
    monkeypatch.setattr('sys.argv', ['tuney', '--preset=white-notes', 'abc'])

    with pytest.raises(SystemExit) as exc_info:
        cli(Tuney, prog='tuney')

    assert exc_info.value.code is None
    assert captured[0].preset == 'white-notes'
    assert captured[0].player.scale.notes == 'ABCDEFG'
    assert captured[0].text == 'abc'
