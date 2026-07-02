from pathlib import Path

import pytest

from pyinstaller_entrypoint import app_args, main
from tuney.audio import midi as midi_module

PYINSTALLER_DEPENDENCY_FLAGS = [
    '--disable-windowed-traceback',
    '--hidden-import mido.backends.rtmidi',
    '--hidden-import pynput.keyboard._win32',
    '--hidden-import pynput._util.win32',
    '--hidden-import pynput._util.win32_vks',
    '--hidden-import _sounddevice',
    '--hidden-import _soundfile',
    '--collect-binaries _sounddevice_data',
    '--collect-binaries _soundfile_data',
]


def test_frozen_app_defaults_to_gui_when_launched_without_arguments() -> None:
    assert app_args(['Tuney'], frozen=True) == ['Tuney', '--gui']


def test_frozen_app_preserves_explicit_arguments() -> None:
    assert app_args(['Tuney', '--help'], frozen=True) == ['Tuney', '--help']


def test_regular_script_preserves_cli_default() -> None:
    assert app_args(['pyinstaller_entrypoint.py'], frozen=False) == [
        'pyinstaller_entrypoint.py'
    ]


def test_internal_midi_output_mode_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        'sys.argv',
        ['Tuney', midi_module.INTERNAL_LIST_MIDI_OUTPUTS],
    )
    monkeypatch.setattr(midi_module, '_output_names', lambda: ['synth'])

    main()

    assert capsys.readouterr().out == '["synth"]\n'


def test_release_builds_bundle_dynamic_runtime_dependencies() -> None:
    release_script = Path('scripts/release.sh').read_text()
    release_workflow = Path('.github/workflows/release-builds.yml').read_text()

    for flag in PYINSTALLER_DEPENDENCY_FLAGS:
        assert flag in release_script
        assert flag in release_workflow


def test_frozen_entrypoint_logs_uncaught_errors(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setattr('sys.argv', ['Tuney'])
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

    def fail(argv: list[str], *, frozen: bool) -> list[str]:
        raise RuntimeError(f'{argv=} {frozen=}')

    monkeypatch.setattr('pyinstaller_entrypoint.app_args', fail)

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 1
    log = tmp_path / 'tuney' / 'tuney.log'
    text = log.read_text()
    assert 'RuntimeError' in text
    assert "argv=['Tuney'] frozen=True" in text
