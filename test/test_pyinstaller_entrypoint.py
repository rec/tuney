from pathlib import Path

import pytest

from install import pyinstaller_entrypoint
from install.pyinstaller_entrypoint import app_args, main
from tuney import midi as midi_module
from tuney.app import platform_info

PYINSTALLER_COMMON_DEPENDENCY_FLAGS = [
    'uv run --with pyinstaller --with pillow pyinstaller',
    '--disable-windowed-traceback',
    '--hidden-import mido.backends.rtmidi',
    '--hidden-import _sounddevice',
    '--hidden-import _soundfile',
    '--collect-binaries _sounddevice_data',
    '--collect-binaries _soundfile_data',
]
PYINSTALLER_LOCAL_PLATFORM_FLAGS = [
    '--hidden-import pynput.keyboard._darwin',
    '--hidden-import pynput._util.darwin',
    '--hidden-import pynput.keyboard._xorg',
    '--hidden-import pynput._util.xorg',
    '--hidden-import pynput._util.uinput',
]
PYINSTALLER_WORKFLOW_PLATFORM_FLAGS = [
    '--hidden-import pynput.keyboard._win32',
    '--hidden-import pynput._util.win32',
    '--hidden-import pynput._util.win32_vks',
    *PYINSTALLER_LOCAL_PLATFORM_FLAGS,
]


def test_frozen_app_defaults_to_gui_when_launched_without_arguments() -> None:
    assert app_args(['Tuney'], frozen=True) == ['Tuney', '--gui']


def test_frozen_app_preserves_explicit_arguments() -> None:
    assert app_args(['Tuney', '--help'], frozen=True) == ['Tuney', '--help']


def test_regular_script_preserves_cli_default() -> None:
    assert app_args(['install/pyinstaller_entrypoint.py'], frozen=False) == [
        'install/pyinstaller_entrypoint.py'
    ]


def test_internal_midi_output_mode_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        'sys.argv',
        ['Tuney', midi_module.INTERNAL_LIST_MIDI_OUTPUTS],
    )
    monkeypatch.setattr(
        pyinstaller_entrypoint, 'output_names_json', lambda: '["synth"]'
    )

    main()

    assert capsys.readouterr().out == '["synth"]\n'


def test_internal_midi_input_mode_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        'sys.argv',
        ['Tuney', midi_module.INTERNAL_LIST_MIDI_INPUTS],
    )
    monkeypatch.setattr(
        pyinstaller_entrypoint, 'input_names_json', lambda: '["keyboard"]'
    )

    main()

    assert capsys.readouterr().out == '["keyboard"]\n'


def test_release_builds_bundle_dynamic_runtime_dependencies() -> None:
    release_script = Path('scripts/release.sh').read_text()
    release_workflow = Path('.github/workflows/release-builds.yml').read_text()

    for flag in PYINSTALLER_COMMON_DEPENDENCY_FLAGS:
        assert flag in release_script
        assert flag in release_workflow

    for flag in PYINSTALLER_LOCAL_PLATFORM_FLAGS:
        assert flag in release_script

    for flag in PYINSTALLER_WORKFLOW_PLATFORM_FLAGS:
        assert flag in release_workflow


def test_macos_release_artifact_archives_one_source() -> None:
    release_workflow = Path('.github/workflows/release-builds.yml').read_text()

    broken_command = (
        'ditto -c -k --keepParent "${{ matrix.dist-path }}" README-MACOS.txt'
    )

    assert broken_command not in release_workflow
    assert 'ditto -c -k macos-package "$ARTIFACT_NAME"' in release_workflow


def test_windows_release_uses_flat_onedir_layout_for_pyside() -> None:
    release_workflow = Path('.github/workflows/release-builds.yml').read_text()
    command = next(
        i.strip()
        for i in release_workflow.splitlines()
        if i.strip().startswith(
            'run: uv run --with pyinstaller --with pillow pyinstaller'
        )
        and '--version-file windows-version-info.txt' in i
    )

    assert '--contents-directory .' in command


def test_frozen_entrypoint_logs_uncaught_errors(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setattr('sys.argv', ['Tuney'])
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    messages = []

    def fail(argv: list[str], *, frozen: bool) -> list[str]:
        raise RuntimeError(f'{argv=} {frozen=}')

    def show_frozen_exception(error: BaseException, path: Path) -> None:
        messages.append((error, path))

    monkeypatch.setattr('install.pyinstaller_entrypoint.app_args', fail)
    monkeypatch.setattr(platform_info, 'show_frozen_exception', show_frozen_exception)

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 1
    log = tmp_path / 'tuney' / 'tuney.txt'
    text = log.read_text()
    assert 'RuntimeError' in text
    assert "argv=['Tuney'] frozen=True" in text
    assert len(messages) == 1
    message_error, message_path = messages[0]
    assert isinstance(message_error, RuntimeError)
    assert message_path == log
