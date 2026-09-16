from pathlib import Path

import pytest

from tuney.app.app import App
from tuney.app.main import main


@pytest.mark.parametrize(
    ('filename', 'contents'),
    [
        ('missing.toml', None),
        ('broken.toml', '['),
        ('broken.json', '{'),
        ('list.json', '[]'),
        ('unknown.txt', 'text'),
    ],
)
def test_invalid_configuration_exits_with_a_message(
    monkeypatch, tmp_path: Path, filename: str, contents: str | None
) -> None:
    path = tmp_path / filename
    if contents is not None:
        path.write_text(contents)
    monkeypatch.setattr('sys.argv', ['tuney', '--config-file', str(path)])
    monkeypatch.setattr(App, 'run', unexpected_run)
    with pytest.raises(SystemExit) as error:
        main()
    assert isinstance(error.value.code, str)
    assert error.value.code


def test_unknown_preset_exits_with_a_message(monkeypatch) -> None:
    monkeypatch.setattr('sys.argv', ['tuney', '--preset', 'nonexistent-test-preset'])
    monkeypatch.setattr(App, 'run', unexpected_run)
    with pytest.raises(SystemExit) as error:
        main()
    assert 'nonexistent-test-preset' in str(error.value.code)


def test_unexpected_runtime_error_is_not_hidden(monkeypatch) -> None:
    def fail(self: App) -> None:
        raise ValueError('unexpected runtime bug')

    monkeypatch.setattr('sys.argv', ['tuney', 'a'])
    monkeypatch.setattr(App, 'run', fail)
    with pytest.raises(ValueError, match='unexpected runtime bug'):
        main()


def unexpected_run(self: App) -> None:
    raise AssertionError('Invalid input must not start the application')
