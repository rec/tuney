import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import tuney.presets
import tuney.time.sequencer
from tuney.app.app import App, run
from tuney.app.main import main
from tuney.app.platform_info import (
    crash_marker_path,
    instance_lock_path,
)
from tuney.audio.mixer import NotePress
from tuney.audio.player import Player
from tuney.time.char_press import CharPress
from tuney.ui import startup


def test_cli_playback_does_not_write_persistent_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    roots = isolate_persistent_roots(monkeypatch, tmp_path)
    mock_live_audio(monkeypatch)

    run(App(text=[CharPress('a', time=0), CharPress('a', False, 0)]))

    assert_persistent_roots_are_empty(roots)


def test_cli_preset_does_not_write_persistent_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    roots = isolate_persistent_roots(monkeypatch, tmp_path)
    mock_live_audio(monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['tuney', '--preset=white-notes', 'abc'])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code is None
    assert_persistent_roots_are_empty(roots)


def test_cli_config_file_does_not_write_persistent_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    roots = isolate_persistent_roots(monkeypatch, tmp_path)
    config = tmp_path / 'config.toml'
    config.write_text('max_gap = 2.0\n')
    mock_live_audio(monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['tuney', '--config-file', str(config), 'abc'])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code is None
    assert_persistent_roots_are_empty(roots)


def test_cli_output_only_writes_explicit_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    roots = isolate_persistent_roots(monkeypatch, tmp_path)
    output = tmp_path / 'out.wav'

    def render_file(
        self: Player,
        path: Path,
        events: list[tuple[int, NotePress]],
        comment: Callable[[], str],
    ) -> None:
        path.write_bytes(b'wav')

    monkeypatch.setattr(Player, 'render_file', render_file)

    run(App(output=output, silent=True, text='a'))

    assert output.read_bytes() == b'wav'
    assert_persistent_roots_are_empty(roots)


def test_interrupted_cli_output_removes_partial_file_without_persistence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    roots = isolate_persistent_roots(monkeypatch, tmp_path)
    output = tmp_path / 'out.wav'

    def render_file(
        self: Player,
        path: Path,
        events: list[tuple[int, NotePress]],
        comment: Callable[[], str],
    ) -> None:
        path.write_bytes(b'partial')
        raise KeyboardInterrupt

    monkeypatch.setattr(Player, 'render_file', render_file)

    with pytest.raises(KeyboardInterrupt):
        run(App(output=output, silent=True, text='a'))

    assert not output.exists()
    assert_persistent_roots_are_empty(roots)


def isolate_persistent_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> list[Path]:
    state_home = tmp_path / 'state-home'
    config_home = tmp_path / 'config-home'
    user_presets = tmp_path / 'user-presets'
    monkeypatch.setenv('XDG_STATE_HOME', str(state_home))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(config_home))
    monkeypatch.setattr(startup, 'autosave_file', state_home / 'tuney' / 'state.toml')
    monkeypatch.setattr(tuney.presets, 'USER_PRESETS', user_presets)
    return [state_home, config_home, user_presets]


def mock_live_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]

    def wait(_event: object, timeout: float | None = None) -> bool:
        if timeout is not None:
            clock[0] += timeout
        return False

    monkeypatch.setattr(tuney.time.sequencer.time, 'time', lambda: clock[0])
    monkeypatch.setattr(tuney.time.sequencer.Event, 'wait', wait)
    monkeypatch.setattr(Player, 'on_note', lambda self, note, is_press: True)
    monkeypatch.setattr(Player, 'stop_all', lambda self: None)
    monkeypatch.setattr(Player, 'wait', lambda self: None)
    monkeypatch.setattr(Player, 'close', lambda self: None)


def assert_persistent_roots_are_empty(roots: list[Path]) -> None:
    assert not crash_marker_path().exists()
    assert not instance_lock_path().exists()
    assert [p for r in roots if r.exists() for p in r.rglob('*') if p.is_file()] == []
