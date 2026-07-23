import re
from pathlib import Path

import pytest
import tyro

from tuney.app.app import App
from tuney.app.main import main
from tuney.time.char_press import CharPress

LONG_OPTION_RE = re.compile(r'(?<![\w.-])--[a-z0-9][a-z0-9.-]*')
SHORT_OPTION_RE = re.compile(r'(?<![\w-])-[^-\s]')
OPTIONS_WITHOUT_SHORT_ALIAS = {
    '--hover-time',
    '--use-speech',
    '--use-phrase-mode',
    '--speech-level',
    '--speech-speed',
    '--speech-voice',
    '--backspace-repeat-delay',
    '--backspace-repeat-rate',
    '--device.sample-rate',
    '--device.dtype',
    '--sound.polyphony.headroom',
    '--sound.polyphony.max-voices',
    '--sound.binaural.enable',
    '--sound.binaural.frequency',
    '--sound.binaural.width',
    '--tuning.type',
    '--table',
    '--midi.input.enable',
    '--midi.input.name',
    '--midi.input.channel',
    '--midi.output.enable',
    '--midi.output.name',
    '--midi.output.channel',
    '--midi.output.program',
    '--midi.output.volume',
    '--midi.output.velocity',
    '--midi.output.note-offset',
    '--midi.output.mute-audio-when-midi-enabled',
    '--midi.output.send-tuning',
    '--text-timings.space',
    '--text-timings.comma',
    '--text-timings.colon',
    '--text-timings.semicolon',
    '--text-timings.blank-line',
    '--text-timings.dot',
    '--text-timings.overlap',
    '--text-timings.seed',
    '--text-timings.alpha-only',
    '--text-timings.strip-accents',
    '--text-timings.scale',
    '--text-timings.other',
    '--text-timings.timings',
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
    capsys,
    file_regression,
    monkeypatch,
) -> None:
    monkeypatch.setenv('COLUMNS', '120')
    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setattr('sys.argv', ['tuney', '--help'])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    file_regression.check(_strip_line_end_padding(capsys.readouterr().out))


def _strip_line_end_padding(text: str) -> str:
    return '\n'.join(_normalize_help_line(line).rstrip() for line in text.splitlines())


def _normalize_help_line(line: str) -> str:
    return line.replace('    \u2022 ', '    - ').replace('    \ufffd ', '    - ')


def test_cli_help_uses_unique_names(
    capsys,
    monkeypatch,
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
    positive_long_options = [option for option in long_options if '.no-' not in option]

    assert len(positive_long_options) == len(set(positive_long_options))
    assert '--midi.output.name' in positive_long_options
    assert '--midi-output' not in positive_long_options
    assert '--player.period' not in help_text


def test_cli_help_gives_expected_public_options_a_short_alias(
    capsys,
    monkeypatch,
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


def test_cli_accepts_public_long_options() -> None:
    app = tyro.cli(
        App,
        args=[
            '--alphabet=abc',
            '--midi.input.enable',
            '--midi.input.channel=3',
            '--midi.output.name=Port',
            '--midi.output.channel=3',
            '--midi.output.program=40',
            '--midi.output.volume=72',
            '--midi.output.velocity=80',
            '--midi.output.note-offset=12',
            '--text-timings.dot=301',
            '--text-timings.scale=4',
            '--text-timings.space=101',
            '--text-timings.comma=201',
            '--text-timings.colon=401',
            '--text-timings.semicolon=402',
            '--text-timings.blank-line=1001',
            '--text-timings.overlap=19',
            '--text-timings.seed=42',
            '--text-timings.alpha-only',
            '--text-timings.strip-accents',
            '--text-timings.other',
            '!',
            '500',
            '--text-timings.timings',
            '10',
            '20',
        ],
    )

    assert app.mapper.alphabet == 'abc'
    assert app.midi.input.enable
    assert app.midi.input.mido_channel == 2
    assert app.midi.output.name == 'Port'
    assert app.midi.output.channel == 3
    assert app.midi.output.program == 40
    assert app.midi.output.volume == 72
    assert app.midi.output.velocity == 80
    assert app.midi.output.note_offset == 12
    assert app.text_timings.dot == 301
    assert app.text_timings.scale == 4
    assert app.text_timings.space == 101
    assert app.text_timings.comma == 201
    assert app.text_timings.colon == 401
    assert app.text_timings.semicolon == 402
    assert app.text_timings.blank_line == 1001
    assert app.text_timings.overlap == 19
    assert app.text_timings.seed == 42
    assert app.text_timings.alpha_only
    assert app.text_timings.strip_accents
    assert app.text_timings.other == {'!': 500}
    assert app.text_timings.timings == [10, 20]


@pytest.mark.parametrize(
    'option',
    ['--midi-in-enable', '--midi-in-channel=3', '--midi-enable', '--midi-channel=3'],
)
def test_cli_rejects_removed_flat_midi_base_options(option: str) -> None:
    with pytest.raises(SystemExit):
        tyro.cli(App, args=[option])


def test_cli_rejects_old_nested_options() -> None:
    with pytest.raises(SystemExit):
        tyro.cli(App, args=['--player.oscillator.period=2'])


def test_cli_accepts_single_character_aliases() -> None:
    app = tyro.cli(
        App,
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
            'tuning.computed:computed',
            '-v',
            '7',
            '-V',
            '19',
            '-J',
            '3',
        ],
    )

    assert app.preset == 'white-notes'
    assert app.config_file == Path('config.toml')
    assert app.text == 'text'
    assert app.max_gap == 3
    assert not app.gui
    assert app.silent
    assert app.output == Path('out.wav')
    assert app.run_in_background
    assert app.mapper.alphabet == 'abc'
    assert app.mapper.length == 3
    assert app.mapper.case_sensitive
    assert app.mapper.invert
    assert app.mapper.offset == 1
    assert app.mapper.range_limit == 12
    assert app.mapper.limiter.value == 'reflect'
    assert app.tuning.detune == 5
    assert app.tuning.computed is not None
    assert app.tuning.computed.limit == 7
    assert app.tuning.computed.notes_per_octave == 19
    assert app.tuning.computed.octave_ratio == 3
    assert app.tuning.root_frequency == 442
    assert app.tuning.root_note == 70


def test_removed_single_character_aliases_are_not_options() -> None:
    with pytest.raises(SystemExit):
        tyro.cli(App, args=['-H', '0.5'])


def test_cli_accepts_text_option() -> None:
    app = tyro.cli(App, args=['--text=Now is the time'])

    assert not app.gui
    assert app.text == 'Now is the time'


def test_cli_uses_positional_arguments_as_text() -> None:
    app = tyro.cli(App, args=['Now', 'is', 'the', 'time'])

    assert app.text == 'Now is the time'


def test_cli_treats_positional_config_file_as_text() -> None:
    app = tyro.cli(App, args=['config.toml'])

    assert app.config_file is None
    assert app.text == 'config.toml'


def test_cli_preserves_char_presses_from_config_default() -> None:
    text = [CharPress('a', time=0)]

    app = tyro.cli(App, args=[], default=App(text=text))

    assert app.text == text


def test_cli_positional_text_replaces_default_char_presses() -> None:
    default = App(text=[CharPress('a', time=0), CharPress('a', False, 100)])

    app = tyro.cli(App, args=['new', 'text'], default=default)

    assert app.text == 'new text'
    assert app.char_presses != default.char_presses


def test_output_option_forces_cli_mode() -> None:
    app = tyro.cli(App, args=['--output=out.wav', '--text=a'])

    assert app.output == Path('out.wav')
    assert not app.gui


def test_gui_option_opens_gui_mode() -> None:
    app = tyro.cli(App, args=['--gui'])

    assert app.gui


def test_cli_loads_preset_defaults(monkeypatch) -> None:
    captured: list[App] = []

    def call(app: App) -> None:
        captured.append(app)

    monkeypatch.setattr('tuney.app.main.run', call)
    monkeypatch.setattr('sys.argv', ['tuney', '--preset=white-notes', 'abc'])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code is None
    assert captured[0].preset == 'white-notes'
    assert captured[0].scale.notes == 'ABCDEFG'
    assert captured[0].text == 'abc'


def test_cli_skips_startup_files_when_gui_starts_with_modifier(
    monkeypatch,
) -> None:
    captured: list[App] = []

    def call(app: App) -> None:
        captured.append(app)

    monkeypatch.setattr('tuney.app.main.run', call)
    monkeypatch.setattr('tuney.ui.startup.set_gui', lambda _: None)
    monkeypatch.setattr('tuney.ui.startup.startup_modifier_held', lambda: True)
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
        main()

    assert exc_info.value.code is None
    assert captured[0].preset is None
    assert captured[0].config_file is None
    assert captured[0].scale.notes != 'ABCDEFG'
    assert captured[0].text == 'abc'
