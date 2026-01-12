import pytest

from tuney.note import canonical, make_note

NOTES = ["C", "C#", "G♯", "C-2", "F♭10"]


@pytest.mark.parametrize("note", NOTES)
def test_note(note):
    actual = str(make_note(note))

    assert actual == canonical(note)
