import pytest
from pytest_regressions.file_regression import FileRegressionFixture

from tuney.__main__ import main


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
