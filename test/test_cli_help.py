from pathlib import Path

import pytest
import tyro
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.__main__ import main
from tuney.char_press import CharPress
from tuney.tuney import Tuney


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
