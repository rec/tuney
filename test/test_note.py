from tuney.note import Note


def test_note():
    assert str(Note.make("C")) == "C"
