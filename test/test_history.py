from pathlib import Path

import pytest

from test._test_app_keys import HistoryApp
from tuney.presets import preset
from tuney.ui import history


def test_text_undo_and_redo_never_read_or_rewrite_presets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(preset, 'USER_PRESETS', tmp_path)
    path = tmp_path / 'external.toml'

    def unexpected_read(names: list[str]) -> dict[str, bytes | None]:
        pytest.fail('Text history must not read presets')

    monkeypatch.setattr(history, 'user_preset_snapshot', unexpected_read)
    window = HistoryApp()
    window.history.checkpoint_undo()
    window.app.max_gap = 2.0
    path.write_text('max_gap = 3.0')

    window.history.undo()
    assert window.app.max_gap == 1.0
    assert path.read_text() == 'max_gap = 3.0'

    path.write_text('max_gap = 4.0')
    window.history.redo()
    assert window.app.max_gap == 2.0
    assert path.read_text() == 'max_gap = 4.0'


def test_preset_delete_undo_and_redo_preserve_unrelated_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(preset, 'USER_PRESETS', tmp_path)
    preset.write_preset('mine', {'max_gap': 2.0})
    original = (tmp_path / 'mine.toml').read_bytes()
    window = HistoryApp()
    with window.history.preset_edit(['mine']):
        preset.delete_presets(['mine'])
    external = tmp_path / 'external.toml'
    external.write_text('max_gap = 3.0')

    window.history.undo()
    assert (tmp_path / 'mine.toml').read_bytes() == original
    assert external.read_text() == 'max_gap = 3.0'

    window.history.redo()
    assert not (tmp_path / 'mine.toml').exists()
    assert external.read_text() == 'max_gap = 3.0'


def test_preset_save_undo_and_redo_restore_only_that_edit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(preset, 'USER_PRESETS', tmp_path)
    window = HistoryApp()
    path = tmp_path / 'mine.toml'
    path.write_text('max_gap = 2.0')
    with window.history.preset_edit(['mine']):
        path.write_text('max_gap = 3.0')

    window.history.undo()
    assert path.read_text() == 'max_gap = 2.0'
    window.history.redo()
    assert path.read_text() == 'max_gap = 3.0'


def test_conflicting_external_edit_cancels_preset_undo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(preset, 'USER_PRESETS', tmp_path)
    messages: list[str] = []
    monkeypatch.setattr(
        history.QMessageBox, 'critical', lambda w, t, m: messages.append(m)
    )
    window = HistoryApp()
    path = tmp_path / 'mine.toml'
    with window.history.preset_edit(['mine']):
        path.write_text('max_gap = 2.0')
    path.write_text('max_gap = 3.0')

    window.history.undo()

    assert path.read_text() == 'max_gap = 3.0'
    assert len(window.history.undo_stack) == 1
    assert not window.history.redo_stack
    assert len(messages) == 1
    assert 'changed outside this edit' in messages[0]


def test_preset_restore_write_failure_preserves_all_existing_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(preset, 'USER_PRESETS', tmp_path)
    first = tmp_path / 'first.toml'
    second = tmp_path / 'second.toml'
    first.write_text('max_gap = 1.0')
    second.write_text('max_gap = 2.0')
    before = preset.user_preset_snapshot(['first', 'second'])
    first.write_text('max_gap = 3.0')
    second.write_text('max_gap = 4.0')
    after = preset.user_preset_snapshot(['first', 'second'])
    write = Path.write_bytes
    writes = 0

    def fail_second_write(self: Path, data: bytes) -> int:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError('disk full')
        return write(self, data)

    monkeypatch.setattr(Path, 'write_bytes', fail_second_write)
    with pytest.raises(OSError, match='disk full'):
        preset.restore_user_preset_snapshot(before, after)

    assert first.read_text() == 'max_gap = 3.0'
    assert second.read_text() == 'max_gap = 4.0'
    assert sorted(tmp_path.iterdir()) == [first, second]
