import pytest

from tuney.audio.multi_player import MultiPlayer
from tuney.char_press import CharPress
from tuney.tuney import Tuney


class FakeApp:
    is_replaying = False
    is_saving = False
    has_focus = True

    class layout:
        @staticmethod
        def set_text(_: str) -> None:
            pass

    @staticmethod
    def on_char(_: CharPress) -> None:
        pass


def test_recorded_char_press_uses_time_relative_to_first_key_press():
    tuney = Tuney()

    actual = [
        tuney.recorded_char_press(CharPress('a', True, 1_700_000_000.0)),
        tuney.recorded_char_press(CharPress('a', False, 1_700_000_000.25)),
        tuney.recorded_char_press(CharPress('b', True, 1_700_000_001.0)),
    ]

    assert actual == [
        CharPress('a', True, 0.0),
        CharPress('a', False, 250.0),
        CharPress('b', True, 1000.0),
    ]


def test_recorded_char_press_reuses_deleted_time_for_next_insert():
    tuney = Tuney()
    assert tuney.recorded_char_press(CharPress('a', True, 100.0)) == CharPress(
        'a', True, 0.0
    )
    tuney._recording_insert_time = 0.0

    actual = [
        tuney.recorded_char_press(CharPress('b', True, 110.0)),
        tuney.recorded_char_press(CharPress('b', False, 110.25)),
        tuney.recorded_char_press(CharPress('c', True, 111.0)),
    ]

    assert actual == [
        CharPress('b', True, 0.0),
        CharPress('b', False, 250.0),
        CharPress('c', True, 1000.0),
    ]


def test_recorded_char_press_caps_silent_gap():
    tuney = Tuney(max_gap=0.5)
    for c in [
        CharPress('a', True, 100.0),
        CharPress('a', False, 100.25),
    ]:
        tuney.char_presses.append(tuney.recorded_char_press(c))

    actual = [
        tuney.recorded_char_press(CharPress('b', True, 110.0)),
        tuney.recorded_char_press(CharPress('b', False, 110.25)),
    ]

    assert actual == [
        CharPress('b', True, 750.0),
        CharPress('b', False, 1000.0),
    ]


def test_recorded_char_press_does_not_cap_time_while_note_is_held():
    tuney = Tuney(max_gap=0.5)
    tuney.char_presses.append(tuney.recorded_char_press(CharPress('a', True, 100.0)))

    actual = tuney.recorded_char_press(CharPress('b', True, 110.0))

    assert actual == CharPress('b', True, 10000.0)


def test_display_text_uses_only_key_presses():
    tuney = Tuney(
        text=[
            CharPress('a', True, 0.0),
            CharPress('a', False, 250.0),
            CharPress('b', True, 1000.0),
            CharPress('b', False, 1250.0),
        ]
    )

    assert tuney.display_text == 'ab'


def test_clear_resets_recording_state():
    tuney = Tuney(text=[CharPress('a', True, 0.0)])
    object.__setattr__(tuney, 'app', FakeApp())
    tuney._recording_start_time = 100.0
    tuney._recording_time_offset = 20.0
    tuney._recording_insert_time = 10.0
    tuney._replay_text = 'a'

    tuney.clear()

    assert tuney.char_presses == []
    assert tuney._recording_start_time is None
    assert tuney._recording_time_offset == 0.0
    assert tuney._recording_insert_time is None
    assert tuney._replay_text == ''


def test_on_char_ignores_input_while_saving():
    tuney = Tuney()
    app = FakeApp()
    app.is_saving = True
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('a', True, 100.0))

    assert tuney.char_presses == []


def test_on_char_ignores_input_without_app_focus():
    tuney = Tuney()
    app = FakeApp()
    app.has_focus = False
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('a', True, 100.0))

    assert tuney.char_presses == []


def test_cli_mode_plays_recorded_events_without_gui(monkeypatch) -> None:
    events: list[tuple[int, bool]] = []
    lifecycle: list[str] = []
    monkeypatch.setattr(
        MultiPlayer,
        'on_note',
        lambda self, note, is_press: events.append((note, is_press)) or True,
    )
    monkeypatch.setattr(
        MultiPlayer, 'stop_all', lambda self: lifecycle.append('stop_all')
    )
    monkeypatch.setattr(MultiPlayer, 'wait', lambda self: lifecycle.append('wait'))
    monkeypatch.setattr(MultiPlayer, 'close', lambda self: lifecycle.append('close'))
    tuney = Tuney(
        cli=True,
        text=[
            CharPress('a', True, 0),
            CharPress('a', False, 0),
        ],
    )

    tuney()

    assert events == [(0, True), (0, False)]
    assert lifecycle == ['stop_all', 'wait', 'close']
    assert 'app' not in tuney.__dict__
    assert 'listener' not in tuney.__dict__


def test_cli_mode_requires_text() -> None:
    with pytest.raises(SystemExit, match='CLI mode requires text to play'):
        Tuney(cli=True)()


def test_cli_mode_requires_sound() -> None:
    with pytest.raises(SystemExit, match='CLI mode requires sound'):
        Tuney(cli=True, disable_sound=True, text='a')()
