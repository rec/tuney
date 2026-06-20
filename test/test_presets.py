from pathlib import Path

import pytest

from tuney.char_press import CharPress
from tuney.presets import preset_names, read_preset
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
    tuney.char_presses.append(CharPress('a', time=0))

    tuney.apply_preset('white-notes')

    assert tuney.preset == 'white-notes'
    assert tuney.player.scale.notes == 'ABCDEFG'
    assert tuney.char_presses == [CharPress('a', time=0)]


def test_tuney_applies_preset_without_recreating_runtime_objects() -> None:
    tuney = Tuney(gui=True)
    app = object()
    listener = object()
    object.__setattr__(tuney, 'app', app)
    object.__setattr__(tuney, 'listener', listener)

    tuney.apply_preset('white-notes')

    assert tuney.app is app
    assert tuney.listener is listener
