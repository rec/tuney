import json
import tomllib

import pytest
import tomlkit

from tuney.serialize import serialize
from tuney.time.char_press import CharPress
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney
from tuney.tuney_state import TuneyState


def test_tuney_dump_data_uses_recorded_char_presses():
    tuney = Tuney()
    state = TuneyState(tuney)
    state.char_presses.append(CharPress('a', time=0.0))
    state.char_presses.append(CharPress('a', False, 250.0))

    actual = tomllib.loads(tomlkit.dumps(serialize(state.dump_data())))

    assert actual['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0.0},
        {'char': 'a', 'is_press': False, 'time': 250.0},
    ]


def test_tuney_dump_data_excludes_text_file(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('a')
    tuney = Tuney(text_file=path, text_timings=TextTimings(overlap=0, timings=[250]))
    state = TuneyState(tuney)

    actual = tomllib.loads(tomlkit.dumps(serialize(state.dump_data())))

    assert 'text_file' not in actual
    assert actual['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0.0},
        {'char': 'a', 'is_press': False, 'time': 250.0},
    ]


@pytest.mark.parametrize('format_name', ['toml', 'json'])
def test_save(tmp_path, file_regression, format_name) -> None:
    suffix = f'.{format_name}'
    path = tmp_path / f'tuney{suffix}'
    TuneyState(Tuney()).save(path)
    text = path.read_text()

    file_regression.check(text, extension=suffix)


def test_save_rejects_unknown_suffix(tmp_path):
    path = tmp_path / 'tuney.txt'

    with pytest.raises(ValueError, match='Do not understand file'):
        TuneyState(Tuney()).save(path)


def test_dump_toml_uses_serialized_state() -> None:
    state = TuneyState(Tuney(max_gap=2.0))

    actual = tomllib.loads(state.dump_toml())

    assert actual['max_gap'] == 2.0


@pytest.mark.parametrize(
    'text',
    [
        'max_gap = 2.0\n',
        json.dumps({'max_gap': 2.0}),
    ],
)
def test_restore_text_accepts_toml_and_json(text: str) -> None:
    tuney = Tuney(max_gap=1.0)

    TuneyState(tuney).restore_text(text)

    assert tuney.max_gap == 2.0
