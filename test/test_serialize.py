import tomllib

import pytest
import tomlkit

from tuney.keyboard.char_press import CharPress
from tuney.serialize import serialize
from tuney.tuney import Tuney


def test_tuney_dump_data_uses_recorded_char_presses():
    tuney = Tuney()
    tuney.char_presses.append(CharPress('a', time=0.0))
    tuney.char_presses.append(CharPress('a', False, 250.0))

    actual = tomllib.loads(tomlkit.dumps(serialize(tuney.dump_data())))

    assert actual['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0.0},
        {'char': 'a', 'is_press': False, 'time': 250.0},
    ]


@pytest.mark.parametrize('format_name', ['toml', 'json'])
def test_save(tmp_path, file_regression, format_name) -> None:
    suffix = f'.{format_name}'
    path = tmp_path / f'tuney{suffix}'
    Tuney().save(path)
    text = path.read_text()

    file_regression.check(text, extension=suffix)


def test_save_rejects_unknown_suffix(tmp_path):
    path = tmp_path / 'tuney.txt'

    with pytest.raises(ValueError, match='Do not understand file'):
        Tuney().save(path)
