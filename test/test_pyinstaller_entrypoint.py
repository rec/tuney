from pyinstaller_entrypoint import app_args


def test_frozen_app_defaults_to_gui_when_launched_without_arguments() -> None:
    assert app_args(['Tuney'], frozen=True) == ['Tuney', '--gui']


def test_frozen_app_preserves_explicit_arguments() -> None:
    assert app_args(['Tuney', '--help'], frozen=True) == ['Tuney', '--help']


def test_regular_script_preserves_cli_default() -> None:
    assert app_args(['pyinstaller_entrypoint.py'], frozen=False) == [
        'pyinstaller_entrypoint.py'
    ]
