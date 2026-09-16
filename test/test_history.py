from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMessageBox

from test._test_app_keys import HistoryApp
from tuney.app.app import App
from tuney.presets import preset
from tuney.presets.autosave import Autosave, AutosaveRestoreError
from tuney.time.char_press import CharPress
from tuney.ui import file_commands, history
from tuney.ui.replay_controls import on_loop_tempo


def test_text_undo_retains_edits_without_serializing_full_state(monkeypatch) -> None:
    window = HistoryApp()

    def unexpected_snapshot(self: App) -> dict[str, object]:
        pytest.fail('Typing must not serialize configuration or the recorded text')

    monkeypatch.setattr(App, 'dump_data', unexpected_snapshot)
    for i in range(400):
        with window.history.text_edit(len(window.app.char_presses)):
            window.app.char_presses.append(CharPress('a', i % 2 == 0, i * 10))
            window.app.key_recorder.time_offset = i
    assert len(window.history.undo_stack) == 400
    assert all(isinstance(e, history.TextEdit) for e in window.history.undo_stack)
    assert sum(len(e.presses) for e in window.history.undo_stack) == 0
    for _ in range(400):
        window.history.undo()
    assert window.app.char_presses == []
    assert window.app.key_recorder.time_offset == 0
    assert sum(len(e.presses) for e in window.history.redo_stack) == 400
    for _ in range(400):
        window.history.redo()
    assert len(window.app.char_presses) == 400
    assert window.app.key_recorder.time_offset == 399


def test_text_edits_interleave_with_settings_and_restore_recorder_timing() -> None:
    window = HistoryApp()
    window.app.text = 'original'
    window.app.__dict__['char_presses'] = [
        CharPress('a', time=100),
        CharPress('a', False, 200),
    ]
    with window.history.text_edit():
        window.app.key_recorder.delete_last_char(window.app.char_presses)
    assert window.app.dump_data()['text'] == []
    assert window.app.key_recorder.insert_time == 100
    window.history.checkpoint_undo()
    window.app.max_gap = 2
    window.history.undo()
    assert window.app.char_presses == []
    window.history.undo()
    assert window.app.display_text == 'a'
    assert window.app.key_recorder.insert_time is None
    window.history.redo()
    assert window.app.char_presses == []
    assert window.app.key_recorder.insert_time == 100
    window.history.redo()
    assert window.app.max_gap == 2


def test_unchanged_text_can_still_undo_recorder_reset() -> None:
    window = HistoryApp()
    window.app.key_recorder.time_offset = 250
    with window.history.text_edit():
        window.app.key_recorder.clear()
    window.history.undo()
    assert window.app.key_recorder.time_offset == 250
    window.history.redo()
    assert window.app.key_recorder.time_offset == 0


def test_text_edit_keeps_only_changed_middle_and_new_edit_discards_redo() -> None:
    window = HistoryApp()
    window.app.__dict__['char_presses'] = [
        CharPress('a'),
        CharPress('b', time=10),
        CharPress('c', time=20),
    ]
    with window.history.text_edit():
        window.app.char_presses[1] = CharPress('z', time=10)
    edit = window.history.undo_stack[-1]
    assert isinstance(edit, history.TextEdit)
    assert edit.index == 1
    assert edit.remove_count == 1
    assert [c.char for c in edit.presses] == ['b']
    window.history.undo()
    assert window.app.display_text == 'abc'
    with window.history.text_edit(3):
        window.app.char_presses.append(CharPress('d', time=30))
    assert window.history.redo_stack == []


@pytest.mark.parametrize(
    'times', [[100, 100.1, 100.2, 100.3], [100, 100.3, 100.1, 100.2]]
)
def test_recorded_events_and_backspace_round_trip_through_undo(
    monkeypatch, times: list[float]
) -> None:
    window = HistoryApp()
    app = window.app
    app.silent = True
    app.backspace_repeat_delay = -1
    app.__dict__['main_window'] = window
    monkeypatch.setattr(App, '_is_listening', property(lambda _: True))
    snapshots: list[list[CharPress]] = []
    offsets: list[float] = []
    for c, p, t in zip(
        'aabb\b', [True, False, True, False, True], [*times, 100.4], strict=True
    ):
        snapshots.append([e.model_copy(deep=True) for e in app.char_presses])
        offsets.append(app.key_recorder.time_offset)
        app.on_char(CharPress(c, p, t))
    final = [c.model_copy(deep=True) for c in app.char_presses]
    final_insert_time = app.key_recorder.insert_time
    for s, o in zip(reversed(snapshots), reversed(offsets), strict=True):
        window.history.undo()
        assert app.char_presses == s
        assert app.key_recorder.time_offset == o
    for _ in snapshots:
        window.history.redo()
    assert app.char_presses == final
    assert app.key_recorder.insert_time == final_insert_time


@pytest.mark.parametrize('accept', [False, True])
@pytest.mark.parametrize('source', ['user', 'builtin'])
def test_preset_replacement_requires_confirmation_and_can_be_undone(
    monkeypatch, tmp_path: Path, accept: bool, source: str
) -> None:
    user, builtin = tmp_path / 'user', tmp_path / 'builtin'
    user.mkdir()
    builtin.mkdir()
    monkeypatch.setattr(preset, 'USER_PRESETS', user)
    monkeypatch.setattr(preset, 'BUILTIN_PRESETS', builtin)
    original = (user if source == 'user' else builtin) / 'saved.toml'
    original.write_text('max_gap = 3.0\n')
    monkeypatch.setattr(file_commands, 'preset_name', lambda _: 'saved')

    def confirm(
        parent: object, title: str, text: str, buttons: object, default: object
    ) -> QMessageBox.StandardButton:
        assert default == QMessageBox.StandardButton.No
        return (
            QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No
        )

    monkeypatch.setattr(QMessageBox, 'question', confirm)
    window = HistoryApp()
    window.app.max_gap = 2.0
    file_commands.on_save_preset(window)
    if accept:
        assert preset.read_preset('saved')['max_gap'] == 2.0
        window.history.undo()
    else:
        assert window.history.undo_stack == []
    assert preset.read_preset('saved')['max_gap'] == 3.0
    assert original.read_text() == 'max_gap = 3.0\n'


@pytest.mark.parametrize('tempo', ['0', '-1', 'inf', '-inf', 'nan'])
def test_invalid_saved_tempo_recovers_without_losing_text(
    monkeypatch, tmp_path: Path, tempo: str
) -> None:
    path = tmp_path / 'state.toml'
    path.write_text(f'text = "abc"\n[loop]\ntempo = {tempo}\n')
    monkeypatch.setattr('tuney.presets.autosave.startup_modifier_held', lambda: False)
    app = App(gui=True)
    assert isinstance(Autosave(file=path).restore(app), AutosaveRestoreError)
    assert app.display_text == 'abc'
    assert history.History(SimpleNamespace(app=app)).loop_tempo == 1.0
    window = HistoryApp()
    on_loop_tempo(window, tempo)
    assert window.history.loop_tempo == 1.0
    assert window.history.undo_stack == []


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
