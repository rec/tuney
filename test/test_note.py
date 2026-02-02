import pytest

from tuney.scale import twelve_tet as tt

NOTES = ['C1', 'C#3', 'G♯5', 'C-2', 'F♭10']


def canonical(s: str) -> str:
    for k, v in tt.ACCIDENTAL_DICT.items():
        s = s.replace(k, v)
    return s


@pytest.mark.parametrize('note', NOTES)
def test_twelve_tet(note):
    number = tt.name_to_number(note)
    name = tt.number_to_name(number)
    assert tt.name_to_number(name) == number

    assert note == 'F♭10' or name == canonical(note)
