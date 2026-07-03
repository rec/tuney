from pathlib import Path

import pytest

from tuney.presets import preset_names, read_preset
from tuney.time.char_press import CharPress
from tuney.tuney import Tuney


def test_bundled_presets_are_listed() -> None:
    assert {'ambient-text', 'midi-controller', 'white-notes'} <= set(preset_names())


def test_bundled_preset_loads_partial_config() -> None:
    assert read_preset('white-notes') == {'player': {'scale': {'notes': 'ABCDEFG'}}}


def test_preset_rejects_text_data(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / 'bad.toml'
    path.write_text('text = "not a preset"\n')
    monkeypatch.setattr('tuney.presets.USER_PRESETS', tmp_path)

    with pytest.raises(ValueError, match='must not contain text'):
        read_preset('bad')


def test_tuney_applies_preset_without_clearing_recorded_text() -> None:
    tuney = Tuney()
    tuney.state.char_presses.append(CharPress('a', time=0))

    tuney.state.apply_preset('white-notes')

    assert tuney.preset == 'white-notes'
    assert tuney.player.scale.notes == 'ABCDEFG'
    assert tuney.state.char_presses == [CharPress('a', time=0)]


def test_tuney_applies_preset_without_recreating_runtime_objects() -> None:
    tuney = Tuney(gui=True)
    app = object()
    listener = object()
    tuney.state.__dict__['app'] = app
    tuney.state.__dict__['listener'] = listener

    tuney.state.apply_preset('white-notes')

    assert tuney.state.app is app
    assert tuney.state.listener is listener
