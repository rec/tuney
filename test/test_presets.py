import pytest

from tuney.app.app import App, apply_preset
from tuney.presets import (
    delete_presets,
    preset_names,
    read_preset,
    restore_user_preset_snapshot,
    user_preset_snapshot,
    write_preset,
)
from tuney.time.char_press import CharPress


def test_bundled_presets_are_listed() -> None:
    assert {'ambient-text', 'midi-controller', 'white-notes'} <= set(preset_names())


def test_bundled_preset_loads_partial_config() -> None:
    assert read_preset('white-notes') == {'scale': {'notes': 'ABCDEFG'}}


def test_preset_rejects_text_data(monkeypatch, tmp_path) -> None:
    path = tmp_path / 'bad.toml'
    path.write_text('text = "not a preset"\n')
    monkeypatch.setattr('tuney.presets.USER_PRESETS', tmp_path)

    with pytest.raises(ValueError, match='must not contain text'):
        read_preset('bad')


def test_user_presets_can_be_written_deleted_and_restored(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr('tuney.presets.USER_PRESETS', tmp_path)

    write_preset('mine', {'max_gap': 2.0, 'text': 'not a preset'})
    snapshot = user_preset_snapshot()
    delete_presets(['mine'])

    assert not (tmp_path / 'mine.toml').exists()

    restore_user_preset_snapshot(snapshot)

    assert read_preset('mine') == {'max_gap': 2.0}


def test_tuney_applies_preset_without_clearing_recorded_text() -> None:
    app = App()
    app.char_presses.append(CharPress('a', time=0))

    apply_preset(app, 'white-notes')

    assert app.preset == 'white-notes'
    assert app.scale.notes == 'ABCDEFG'
    assert app.char_presses == [CharPress('a', time=0)]


def test_tuney_applies_preset_without_recreating_runtime_objects() -> None:
    app = App(gui=True)
    main_window = object()
    listener = object()
    app.__dict__['main_window'] = main_window
    app.__dict__['listener'] = listener

    apply_preset(app, 'white-notes')

    assert app.main_window is main_window
    assert app.listener is listener
