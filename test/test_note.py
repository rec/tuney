import pytest

from tuney.note import canonical, make_note, Note
from tuney.scale import twelve_tet as tt

NOTES = ["C", "C#", "G♯", "C-2", "F♭10"]


@pytest.mark.parametrize("note", NOTES)
def test_note(note):
    actual = str(make_note(note))

    assert actual == canonical(note)


@pytest.mark.parametrize("note", NOTES)
def test_twelve_tet(note):
    if isinstance((n := make_note(note)), Note):
        actual = n.note_number
        expected = tt.name_to_number(note)
        assert actual == expected
