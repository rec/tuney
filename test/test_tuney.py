import json
import random

import pytest
from PySide6.QtCore import QMimeData

from tuney.app.app import App
from tuney.app.text_timing import edit_text_timing
from tuney.scale.tuning import Computed, TuningSource
from tuney.time.char_press import CharPress
from tuney.time.sequencer import Sequencer
from tuney.time.text_timings import TextTimings
from tuney.ui.file_commands import CHAR_PRESSES_MIME, on_copy_text, on_paste_text
from tuney.ui.history import History
from tuney.ui.key_events import on_key_event
from tuney.ui.main_window import MainWindow

from .app_helpers import (
    FakeApp,
    _FakeClipboard,
    _FakeKeyEvent,
    _ShortcutWindow,
    _TextClipboardWindow,
    recorded_char_press,
)


def test_recorded_char_press_uses_time_relative_to_first_key_press():
    app = App()

    actual = [
        recorded_char_press(app, CharPress('a', time=1_700_000_000.0)),
        recorded_char_press(app, CharPress('a', False, 1_700_000_000.25)),
        recorded_char_press(app, CharPress('b', time=1_700_000_001.0)),
    ]

    assert actual == [
        CharPress('a', time=0.0),
        CharPress('a', False, 250.0),
        CharPress('b', time=1000.0),
    ]


def test_recorded_char_press_reuses_deleted_time_for_next_insert():
    app = App()
    assert recorded_char_press(app, CharPress('a', time=100.0)) == CharPress(
        'a', time=0.0
    )
    app.key_recorder.insert_time = 0.0

    actual = [
        recorded_char_press(app, CharPress('b', time=110.0)),
        recorded_char_press(app, CharPress('b', False, 110.25)),
        recorded_char_press(app, CharPress('c', time=111.0)),
    ]

    assert actual == [
        CharPress('b', time=0.0),
        CharPress('b', False, 250.0),
        CharPress('c', time=1000.0),
    ]


def test_recorded_char_press_caps_silent_gap():
    app = App(max_gap=0.5)
    for c in [
        CharPress('a', time=100.0),
        CharPress('a', False, 100.25),
    ]:
        app.append_char_press(recorded_char_press(app, c))

    actual = [
        recorded_char_press(app, CharPress('b', time=110.0)),
        recorded_char_press(app, CharPress('b', False, 110.25)),
    ]

    assert actual == [
        CharPress('b', time=750.0),
        CharPress('b', False, 1000.0),
    ]


def test_recorded_char_press_appends_to_restored_recording() -> None:
    app = App(
        text=[
            CharPress('a', time=0.0),
            CharPress('a', False, 27123.0),
        ]
    )

    actual = [
        recorded_char_press(app, CharPress('t', time=100.0)),
        recorded_char_press(app, CharPress('t', False, 100.25)),
    ]

    assert actual == [
        CharPress('t', time=27123.0),
        CharPress('t', False, 27373.0),
    ]


def test_recorded_char_press_does_not_cap_time_while_note_is_held():
    app = App(max_gap=0.5)
    app.append_char_press(recorded_char_press(app, CharPress('a', time=100.0)))

    actual = recorded_char_press(app, CharPress('b', time=110.0))

    assert actual == CharPress('b', time=10000.0)


def test_text_char_presses_must_be_sorted() -> None:
    with pytest.raises(ValueError, match='char_presses are not sorted by time'):
        App(text=[CharPress('b', time=1000), CharPress('a', time=0)])


def test_append_char_press_sorts_late_char_press(caplog) -> None:
    app = App()

    app.append_char_press(CharPress('b', time=1000))
    app.append_char_press(CharPress('a', time=0))

    assert app.char_presses == [
        CharPress('a', time=0),
        CharPress('b', time=1000),
    ]
    assert any('Out-of-order char_press' in message for message in caplog.messages)


def test_display_text_uses_only_key_presses():
    app = App(
        text=[
            CharPress('a', time=0.0),
            CharPress('a', False, 250.0),
            CharPress('b', time=1000.0),
            CharPress('b', False, 1250.0),
        ]
    )

    assert app.display_text == 'ab'


def test_display_text_timings_show_offsets() -> None:
    app = App(
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 250.0),
            CharPress('\b', time=300.0),
        ]
    )

    assert app.display_text_timings == [
        ['a', '100', '150'],
        ['\b', '200', ''],
    ]


def test_edit_text_timings_updates_char_presses() -> None:
    app = App(
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 250.0),
            CharPress('b', time=300.0),
        ]
    )

    edit_text_timing(app.char_presses, 0, 0, 'c')
    edit_text_timing(app.char_presses, 1, 1, '500')
    edit_text_timing(app.char_presses, 1, 2, '75')

    assert app.char_presses == [
        CharPress('c', time=100.0),
        CharPress('c', False, 250.0),
        CharPress('b', time=600.0),
        CharPress('b', False, 675.0),
    ]


def test_char_press_negative_time_is_zero() -> None:
    assert CharPress('a', time=-1).time == 0.0


def test_clear_resets_recording_state():
    app = App(gui=True, text=[CharPress('a', time=0.0)], max_gap=2.0)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    app.key_recorder.start_time = 100.0
    app.key_recorder.time_offset = 20.0
    app.key_recorder.insert_time = 10.0
    app.key_recorder.replay_text = 'a'

    app.clear()

    assert app.char_presses == []
    assert app.max_gap == App().max_gap
    assert app.key_recorder.start_time is None
    assert app.key_recorder.time_offset == 0.0
    assert app.key_recorder.insert_time is None
    assert app.key_recorder.replay_text == ''
    assert main_window.undo_count == 1


def test_randomize_timing_replaces_timing_and_keeps_display_text() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 200.0),
            CharPress('b', time=10_000.0),
            CharPress('b', False, 10_500.0),
        ],
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    original_char_presses = list(app.char_presses)
    app.key_recorder.start_time = 100.0
    app.key_recorder.time_offset = 20.0
    app.key_recorder.insert_time = 10.0
    app.key_recorder.replay_text = 'a'

    app.randomize_timing()

    assert app.display_text == 'ab'
    assert app.char_presses != original_char_presses
    assert [c.char for c in app.char_presses if c.is_press] == ['a', 'b']
    assert app.key_recorder.start_time is None
    assert app.key_recorder.time_offset == 0.0
    assert app.key_recorder.insert_time is None
    assert app.key_recorder.replay_text == ''
    assert main_window.undo_count == 1


def test_randomize_settings_changes_valid_scale_and_tuning_only() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 200.0),
        ],
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    text_timings = app.text_timings.model_copy(deep=True)
    char_presses = list(app.char_presses)

    app.randomize_settings(random.Random(1))

    assert type(app).model_validate(app.model_dump())
    assert app.text_timings == text_timings
    assert app.char_presses == char_presses
    assert app.tuning.type == TuningSource.computed
    assert isinstance(app.tuning.computed, Computed)
    assert app.tuning.computed.notes_per_octave == sum(app.scale.intervals)
    assert 5 <= app.tuning.computed.notes_per_octave <= 12
    assert 220 <= app.tuning.root_frequency <= 660
    assert 48 <= app.tuning.root_note <= 72
    assert app.scale.begin == 'A'
    assert app.scale.end == 'G'
    assert app.scale.root in 'ABCDEFG'
    assert main_window.undo_count == 1


def test_text_file_loads_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('ab')
    app = App(
        text_file=path,
        text_timings=TextTimings(seed=1, overlap=0, timings=[10]),
    )

    assert app.display_text == 'ab'
    assert [c.char for c in app.char_presses if c.is_press] == ['a', 'b']


def test_text_file_loads_non_utf8_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_bytes('café'.encode('cp1252'))
    app = App(
        text_file=path,
        text_timings=TextTimings(seed=1, overlap=0, strip_accents=False, timings=[10]),
    )

    assert app.display_text == 'café'


def test_load_text_file_replaces_char_presses(tmp_path) -> None:
    path = tmp_path / 'input.txt'
    path.write_text('ab')
    app = App(
        gui=True,
        text='old',
        text_timings=TextTimings(seed=1, overlap=0, timings=[10]),
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    app.key_recorder.start_time = 100.0

    app.load_text_file(path)

    assert app.display_text == 'ab'
    assert [c.char for c in app.char_presses if c.is_press] == ['a', 'b']
    assert app.key_recorder.start_time is None
    assert main_window.undo_count == 1


def test_on_char_records_undo_for_added_char_press() -> None:
    app = App(gui=True, silent=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('a', time=100.0))

    assert main_window.undo_count == 1


def test_history_checkpoint_ignores_live_sequencer() -> None:
    class FakeWindow:
        def __init__(self) -> None:
            self.app = App(gui=True, text='a')

    window = FakeWindow()
    history = History(window)
    window.app.key_recorder.sequencer = Sequencer(
        char_presses=[CharPress('a', time=60_000)],
        callback=lambda _: None,
    )

    history.checkpoint_undo()

    assert len(history.undo_stack) == 1
    assert history.undo_stack[0].key_recorder.sequencer is None


def test_randomize_on_each_loop_ignores_live_sequencer() -> None:
    class FakeWindow:
        def __init__(self) -> None:
            self.app = App(gui=True, text='a')
            self.history = History(self)

    window = FakeWindow()
    window.app.key_recorder.sequencer = Sequencer(
        char_presses=[CharPress('a', time=60_000)],
        callback=lambda _: None,
    )

    MainWindow.on_randomize_on_each_loop(window, True)

    assert window.history.randomize_on_each_loop


def test_gui_listener_queues_keys_through_app() -> None:
    app = App(gui=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    assert app.keyboard_listener.callback == main_window.on_key


def test_backspace_autorepeat_starts_after_configured_delay() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
        ],
        backspace_repeat_delay=1.5,
        backspace_repeat_rate=4.0,
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('\b', time=200.0))

    assert app.display_text == 'a'
    assert main_window.after_calls[0][1] == 1500


def test_backspace_autorepeat_repeats_at_configured_rate() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
            CharPress('c', time=200.0),
        ],
        backspace_repeat_delay=2.0,
        backspace_repeat_rate=5.0,
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('\b', time=300.0))
    first_callback = main_window.after_calls[0][2]
    assert callable(first_callback)
    first_callback()

    assert app.display_text == 'a'
    assert main_window.after_calls[1][1] == 200


def test_backspace_release_cancels_autorepeat() -> None:
    app = App(gui=True, text=[CharPress('a', time=0.0)])
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('\b', time=100.0))
    app.on_char(CharPress('\b', False, time=200.0))

    assert main_window.cancelled_after_ids == ['after-0']
    assert app.key_recorder.backspace_repeat_after_id is None


def test_backspace_autorepeat_can_be_disabled() -> None:
    app = App(
        gui=True,
        text=[CharPress('a', time=0.0)],
        backspace_repeat_rate=0,
    )
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('\b', time=100.0))

    assert main_window.after_calls == []


def test_copy_text_exports_text_and_char_presses_json() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
    )
    clipboard = _FakeClipboard()
    window = _TextClipboardWindow(app, clipboard)

    on_copy_text(window)

    assert clipboard.mime is not None
    assert clipboard.mime.text() == 'a'
    assert json.loads(bytes(clipboard.mime.data(CHAR_PRESSES_MIME))) == [
        {'char': 'a', 'is_press': True, 'time': 0.0},
        {'char': 'a', 'is_press': False, 'time': 100.0},
    ]
    destination = App(gui=True, text='old')
    pasted = _TextClipboardWindow(destination, clipboard)
    on_paste_text(pasted)
    assert destination.char_presses == app.char_presses
    assert pasted.undo_count == 1
    assert pasted.update_count == 1


@pytest.mark.parametrize('payload', [b'not json', b'{}', b'[{"time":"later"}]'])
def test_invalid_clipboard_timing_keeps_current_text(
    monkeypatch, payload: bytes
) -> None:
    app = App(gui=True, text='old')
    original = list(app.char_presses)
    clipboard = _FakeClipboard('replacement')
    mime = QMimeData()
    mime.setData(CHAR_PRESSES_MIME, payload)
    clipboard.setMimeData(mime)
    window = _TextClipboardWindow(app, clipboard)
    errors: list[str] = []
    monkeypatch.setattr(
        'tuney.ui.file_commands.QMessageBox.critical',
        lambda parent, title, message: errors.append(message),
    )
    on_paste_text(window)
    assert errors
    assert app.char_presses == original
    assert window.undo_count == 0
    assert window.update_count == 0


def test_paste_text_replaces_text_with_timed_clipboard_text() -> None:
    app = App(gui=True, text=[CharPress('x', time=0)])
    clipboard = _FakeClipboard('ab')
    window = _TextClipboardWindow(app, clipboard)

    on_paste_text(window)

    assert app.display_text == 'ab'
    assert window.undo_count == 1
    assert window.update_count == 1


def test_command_copy_and_paste_use_text_clipboard_commands() -> None:
    from PySide6.QtCore import Qt

    window = _ShortcutWindow()

    assert on_key_event(
        window, _FakeKeyEvent(Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier), True
    )
    assert on_key_event(
        window, _FakeKeyEvent(Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier), True
    )

    assert window.calls == ['copy', 'paste']
