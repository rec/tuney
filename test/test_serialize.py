import json
import tomllib

import pytest
import tomlkit

from tuney.char_press import CharPress
from tuney.serialize import serialize
from tuney.tuney import Tuney


def test_serialize_tuney_config_for_toml():
    tuney = Tuney()

    text = tomlkit.dumps(serialize(tuney.dump_data()))
    actual = tomllib.loads(text)

    assert actual['mapper']['map'] == 'linear'
    assert actual['player']['oscillator']['waveform'] == 'triangle'
    Tuney(**actual)


def test_tuney_dump_data_uses_recorded_char_presses():
    tuney = Tuney()
    tuney.char_presses.append(CharPress('a', True, 0.0))
    tuney.char_presses.append(CharPress('a', False, 250.0))

    actual = tomllib.loads(tomlkit.dumps(serialize(tuney.dump_data())))

    assert actual['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0.0},
        {'char': 'a', 'is_press': False, 'time': 250.0},
    ]


def test_save_writes_toml(tmp_path):
    path = tmp_path / 'tuney.toml'

    Tuney().save(path)

    actual = tomllib.loads(path.read_text())
    assert actual['mapper']['map'] == 'linear'
    assert actual['player']['oscillator']['waveform'] == 'triangle'
    Tuney(**actual)


def test_save_writes_json(tmp_path):
    path = tmp_path / 'tuney.json'

    Tuney().save(path)

    actual = json.loads(path.read_text())
    assert actual['mapper']['map'] == 'linear'
    assert actual['player']['oscillator']['waveform'] == 'triangle'
    Tuney(**actual)


def test_save_rejects_unknown_suffix(tmp_path):
    path = tmp_path / 'tuney.txt'

    with pytest.raises(ValueError, match='Do not understand file'):
        Tuney().save(path)
