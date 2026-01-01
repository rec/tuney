import pytest

from tuney.note import canonical, Note

NOTES = ["C", "C#", "G♯", "C-2", "F♭10"]


@pytest.mark.parametrize("note", NOTES)
def test_note(note):
    actual = str(Note.make(note))

    assert actual == canonical(note)
