from tuney.char_press import CharPress
from tuney.tuney import Tuney


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
