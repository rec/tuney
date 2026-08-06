from tuney.keyboard import listener
from tuney.keyboard.listener import KeyboardListener
from tuney.time.char_press import CharPress


class FakeKey:
    def __init__(self, name: str = '', char: str = '') -> None:
        self.name = name
        self.char = char


def test_caps_lock_is_ignored() -> None:
    chars: list[CharPress] = []
    keyboard_listener = KeyboardListener(chars.append)
    keyboard_listener._on(FakeKey(name='caps_lock'), True)
    keyboard_listener._on(FakeKey(name='caps_lock'), False)

    assert chars == []
    assert keyboard_listener.held_keys == set()


def test_character_key_still_emits_char_press() -> None:
    chars: list[CharPress] = []
    keyboard_listener = KeyboardListener(chars.append)

    keyboard_listener._on(FakeKey(char='a'), True)

    assert len(chars) == 1
    assert chars[0].char == 'a'


def test_release_remembers_physical_key_press_char() -> None:
    chars: list[CharPress] = []
    keyboard_listener = KeyboardListener(chars.append)
    key = FakeKey(char='A')

    keyboard_listener._on(key, True)
    key.char = 'a'
    keyboard_listener._on(key, False)

    assert [(c.char, c.is_press, c.pressed_char) for c in chars] == [
        ('A', True, 'A'),
        ('A', False, 'A'),
    ]
    assert keyboard_listener.held_key_chars == {}


def test_command_shortcut_release_is_not_emitted() -> None:
    chars: list[CharPress] = []
    keyboard_listener = KeyboardListener(chars.append)
    key = FakeKey(char='a')

    keyboard_listener._on(FakeKey(name='cmd_l'), True)
    keyboard_listener._on(key, True)
    keyboard_listener._on(key, False)
    keyboard_listener._on(FakeKey(name='cmd_l'), False)

    assert chars == []
    assert keyboard_listener.held_key_chars == {}


def test_listener_is_created_lazily(monkeypatch) -> None:
    created = []
    monkeypatch.setattr(
        listener,
        '_make_listener',
        lambda keyboard_listener: created.append(keyboard_listener)
        or keyboard_listener,
    )

    keyboard_listener = KeyboardListener(lambda _: None)

    assert created == []
    assert keyboard_listener.listener is keyboard_listener
    assert created == [keyboard_listener]
