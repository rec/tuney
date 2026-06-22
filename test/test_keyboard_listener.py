from pynput.keyboard import Key, KeyCode

from tuney.char_press import CharPress
from tuney.keyboard.listener import KeyboardListener


def test_caps_lock_is_ignored() -> None:
    chars: list[CharPress] = []
    listener = KeyboardListener(chars.append)
    listener._on(Key.caps_lock, True)
    listener._on(Key.caps_lock, False)

    assert chars == []
    assert listener.held_keys == set()


def test_character_key_still_emits_char_press() -> None:
    chars: list[CharPress] = []
    listener = KeyboardListener(chars.append)

    listener._on(KeyCode.from_char('a'), True)

    assert len(chars) == 1
    assert chars[0].char == 'a'
