import tuney.keyboard.listener
from tuney.keyboard.listener import KeyboardListener
from tuney.time.char_press import CharPress


class FakeKey:
    def __init__(self, name: str = '', char: str = '') -> None:
        self.name = name
        self.char = char


def test_caps_lock_is_ignored() -> None:
    chars: list[CharPress] = []
    listener = KeyboardListener(chars.append)
    listener._on(FakeKey(name='caps_lock'), True)
    listener._on(FakeKey(name='caps_lock'), False)

    assert chars == []
    assert listener.held_keys == set()


def test_character_key_still_emits_char_press() -> None:
    chars: list[CharPress] = []
    listener = KeyboardListener(chars.append)

    listener._on(FakeKey(char='a'), True)

    assert len(chars) == 1
    assert chars[0].char == 'a'


def test_listener_is_created_lazily(monkeypatch) -> None:
    created = []
    monkeypatch.setattr(
        tuney.keyboard.listener,
        '_make_listener',
        lambda listener: created.append(listener) or listener,
    )

    listener = KeyboardListener(lambda _: None)

    assert created == []
    assert listener.listener is listener
    assert created == [listener]
