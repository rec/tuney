import pytest

from test import twelve_tet

NOTES = ['C1', 'C#3', 'G♯5', 'C-2', 'F♭10']


def canonical(s: str) -> str:
    for k, v in twelve_tet.ACCIDENTAL_DICT.items():
        s = s.replace(k, v)
    return s


@pytest.mark.parametrize('note', NOTES)
def test_twelve_tet(note):
    number = twelve_tet.to_number(note)
    name = twelve_tet.to_name(number)
    assert twelve_tet.to_number(name) == number

    assert note == 'F♭10' or name == canonical(note)
