import tomllib

import pytest
import tomlkit

from tuney.keyboard.char_press import CharPress
from tuney.serialize import serialize
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney


def test_tuney_dump_data_uses_recorded_char_presses():
    tuney = Tuney()
    tuney.state.char_presses.append(CharPress('a', time=0.0))
    tuney.state.char_presses.append(CharPress('a', False, 250.0))

    actual = tomllib.loads(tomlkit.dumps(serialize(tuney.state.dump_data())))

    assert actual['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0.0},
        {'char': 'a', 'is_press': False, 'time': 250.0},
    ]


def test_tuney_dump_data_excludes_text_file(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('a')
    tuney = Tuney(text_file=path, text_timings=TextTimings(overlap=0, timings=[250]))

    actual = tomllib.loads(tomlkit.dumps(serialize(tuney.state.dump_data())))

    assert 'text_file' not in actual
    assert actual['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0.0},
        {'char': 'a', 'is_press': False, 'time': 250.0},
    ]


@pytest.mark.parametrize('format_name', ['toml', 'json'])
def test_save(tmp_path, file_regression, format_name) -> None:
    suffix = f'.{format_name}'
    path = tmp_path / f'tuney{suffix}'
    Tuney().state.save(path)
    text = path.read_text()

    file_regression.check(text, extension=suffix)


def test_save_rejects_unknown_suffix(tmp_path):
    path = tmp_path / 'tuney.txt'

    with pytest.raises(ValueError, match='Do not understand file'):
        Tuney().state.save(path)
