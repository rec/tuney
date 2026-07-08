import re
from pathlib import Path

import pytest
import tyro
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.__main__ import main
from tuney.cli import cli
from tuney.time.char_press import CharPress
from tuney.tuney import Tuney
from tuney.tuney_state import TuneyState

LONG_OPTION_RE = re.compile(r'(?<![\w-])--[a-z0-9][a-z0-9-]*')
SHORT_OPTION_RE = re.compile(r'(?<![\w-])-[^-\s]')
OPTIONS_WITHOUT_SHORT_ALIAS = {
    '--hover-time',
    '--backspace-repeat-delay',
    '--backspace-repeat-rate',
    '--sample-rate',
    '--dtype',
    '--headroom',
    '--max-voices',
    '--midi-enable',
    '--midi-output',
    '--midi-channel',
    '--midi-velocity',
    '--midi-note-offset',
    '--space',
    '--comma',
    '--colon',
    '--semicolon',
    '--blank-line',
    '--dot',
    '--overlap',
    '--seed',
    '--alpha-only',
    '--strip-accents',
    '--scale',
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
    file_regression.check(_strip_line_end_padding(capsys.readouterr().out))


def _strip_line_end_padding(text: str) -> str:
    return '\n'.join(line.rstrip() for line in text.splitlines())


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
    assert '--midi-output' in positive_long_options
    assert '--player.period' not in help_text


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
        if not _has_option(line, OPTIONS_WITHOUT_SHORT_ALIAS)
    ]
    lines_without_short_alias = [
        line
        for line in public_option_lines
        if _has_option(line, OPTIONS_WITHOUT_SHORT_ALIAS)
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


def _has_option(line: str, options: set[str]) -> bool:
    return any(
        re.search(rf'(?<![\w-]){re.escape(option)}(?![\w-])', line)
        for option in options
    )


def test_cli_accepts_flat_long_options() -> None:
    tuney = tyro.cli(
        Tuney,
        args=[
            '--alphabet=abc',
            '--midi-output=Port',
            '--midi-channel=3',
            '--midi-velocity=80',
            '--midi-note-offset=12',
            '--dot=301',
            '--scale=4',
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
    assert tuney.midi.output == 'Port'
    assert tuney.midi.channel == 3
    assert tuney.midi.velocity == 80
    assert tuney.midi.note_offset == 12
    assert tuney.text_timings.dot == 301
    assert tuney.text_timings.scale == 4
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
            '-T',
            '5',
            '-U',
            '442',
            '-W',
            '70',
            'tuning.tuning:computed',
            '-v',
            '7',
            '-V',
            '19',
            '-J',
            '3',
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
    assert tuney.tuning.detune == 5
    assert tuney.tuning.tuning.limit == 7
    assert tuney.tuning.tuning.notes_per_octave == 19
    assert tuney.tuning.tuning.octave_ratio == 3
    assert tuney.tuning.root_frequency == 442
    assert tuney.tuning.root_note == 70


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
    assert TuneyState(tuney).char_presses != TuneyState(default).char_presses


def test_output_option_forces_cli_mode() -> None:
    tuney = tyro.cli(Tuney, args=['--output=out.wav', '--text=a'])

    assert tuney.output == Path('out.wav')
    assert not tuney.gui


def test_gui_option_opens_gui_mode() -> None:
    tuney = tyro.cli(Tuney, args=['--gui'])

    assert tuney.gui


def test_cli_loads_preset_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[TuneyState] = []

    def call(state: TuneyState) -> None:
        captured.append(state)

    monkeypatch.setattr(TuneyState, '__call__', call)
    monkeypatch.setattr('sys.argv', ['tuney', '--preset=white-notes', 'abc'])

    with pytest.raises(SystemExit) as exc_info:
        cli(Tuney, prog='tuney')

    assert exc_info.value.code is None
    assert captured[0].tuney.preset == 'white-notes'
    assert captured[0].tuney.scale.notes == 'ABCDEFG'
    assert captured[0].tuney.text == 'abc'


def test_cli_skips_startup_files_when_gui_starts_with_modifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[TuneyState] = []

    def call(state: TuneyState) -> None:
        captured.append(state)

    monkeypatch.setattr(TuneyState, '__call__', call)
    monkeypatch.setattr('tuney.cli._startup_files_should_be_skipped', lambda _: True)
    monkeypatch.setattr(
        'sys.argv',
        [
            'tuney',
            '--gui',
            '--preset=white-notes',
            '--config-file=missing.toml',
            'abc',
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli(Tuney, prog='tuney')

    assert exc_info.value.code is None
    assert captured[0].tuney.preset is None
    assert captured[0].tuney.config_file is None
    assert captured[0].tuney.skip_startup_files
    assert captured[0].tuney.scale.notes != 'ABCDEFG'
    assert captured[0].tuney.text == 'abc'


def test_startup_file_skip_check_ignores_cli_mode() -> None:
    from tuney.cli import _startup_files_should_be_skipped

    assert not _startup_files_should_be_skipped(Tuney())
