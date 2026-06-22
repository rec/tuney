from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from tuney.char_press import CharPress
from tuney.ui import app as app_module
from tuney.ui.app import App, _event_char


def _key_event(
    key: Qt.Key,
    text: str = '',
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    event_type: QKeyEvent.Type = QKeyEvent.Type.KeyPress,
) -> QKeyEvent:
    return QKeyEvent(event_type, key, modifiers, text)


def test_caps_lock_key_event_has_no_character() -> None:
    assert _event_char(_key_event(Qt.Key.Key_CapsLock)) == ''


def test_text_key_event_uses_text() -> None:
    assert _event_char(_key_event(Qt.Key.Key_A, 'a')) == 'a'


def test_command_modified_key_event_has_no_character() -> None:
    assert (
        _event_char(_key_event(Qt.Key.Key_A, 'a', Qt.KeyboardModifier.MetaModifier))
        == ''
    )


def test_special_key_events_are_mapped_to_characters() -> None:
    assert _event_char(_key_event(Qt.Key.Key_Backspace)) == '\b'
    assert _event_char(_key_event(Qt.Key.Key_Return)) == '\n'


def test_key_events_record_press_and_release_times(monkeypatch) -> None:
    chars: list[CharPress] = []
    app = App.__new__(App)
    app._key_chars = {}
    app.tuney = type('Tuney', (), {'on_char': chars.append})()
    times = iter([100.0, 100.25])
    monkeypatch.setattr(app_module.time, 'time', lambda: next(times))

    app._on_key_event(_key_event(Qt.Key.Key_A, 'A'), True)
    app._on_key_event(
        _key_event(Qt.Key.Key_A, event_type=QKeyEvent.Type.KeyRelease), False
    )

    assert chars == [
        CharPress('A', time=100.0),
        CharPress('A', False, time=100.25),
    ]


def test_caps_lock_key_event_is_ignored() -> None:
    chars: list[CharPress] = []
    app = App.__new__(App)
    app._key_chars = {}
    app.tuney = type('Tuney', (), {'on_char': chars.append})()

    app._on_key_event(_key_event(Qt.Key.Key_CapsLock), True)

    assert chars == []
    assert app._key_chars == {}


def test_event_filter_captures_key_event(monkeypatch) -> None:
    chars: list[CharPress] = []
    app = App.__new__(App)
    app._key_chars = {}
    app.tuney = type('Tuney', (), {'on_char': chars.append})()
    monkeypatch.setattr(
        App, 'focus_in_control_panel', property(lambda self: False)
    )
    monkeypatch.setattr(app_module.time, 'time', lambda: 100.0)

    assert app.eventFilter(app, _key_event(Qt.Key.Key_A, 'a'))
    assert chars == [CharPress('a', time=100.0)]


def test_event_filter_ignores_control_panel_focus(monkeypatch) -> None:
    chars: list[CharPress] = []
    app = App.__new__(App)
    app._key_chars = {}
    app.tuney = type('Tuney', (), {'on_char': chars.append})()
    monkeypatch.setattr(App, 'focus_in_control_panel', property(lambda self: True))

    assert not app.eventFilter(app, _key_event(Qt.Key.Key_A, 'a'))
    assert chars == []
