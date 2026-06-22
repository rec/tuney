import tomllib
from datetime import datetime
from pathlib import Path

import pytest
import soundfile

from tuney.audio.multi_player import MultiPlayer
from tuney.char_press import CharPress
from tuney.time.text_timings import TextTimings
from tuney.tuney import Tuney
from tuney.ui.app import App
from tuney.ui.transport import Action, State


class FakeApp:
    is_replaying = False
    is_saving = False
    loop_replay = False
    loop_before = 0.0
    loop_after = 0.0
    loop_tempo = 1.0
    randomize_on_each_loop = False
    has_focus = True
    focus_in_control_panel = False

    def __init__(self) -> None:
        self.after_calls: list[tuple[str, int, object, tuple[object, ...]]] = []
        self.cancelled_after_ids: list[str] = []
        self.undo_count = 0

    class layout:
        @staticmethod
        def set_text(_: str) -> None:
            pass

    ui = layout

    def record_undo(self) -> None:
        self.undo_count += 1

    def after(self, delay: int, callback: object, *args: object) -> str:
        after_id = f'after-{len(self.after_calls)}'
        self.after_calls.append((after_id, delay, callback, args))
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self.cancelled_after_ids.append(after_id)

    @staticmethod
    def on_char(_: CharPress) -> None:
        pass


class FakeLoop:
    def select(self) -> None:
        pass

    def deselect(self) -> None:
        pass


class FakeLayout:
    loop = FakeLoop()
    randomize_on_each_loop = FakeLoop()

    def set_text(self, _: str) -> None:
        pass

    def rebuild_control_panel(self) -> None:
        pass

    def rebuild_note_grid(self) -> None:
        pass

    def refresh_loop_controls(self) -> None:
        pass

    def set_loop_state(self, loop_replay: bool) -> None:
        if loop_replay:
            self.loop.select()
        else:
            self.loop.deselect()

    def set_randomize_on_each_loop_state(self, randomize_on_each_loop: bool) -> None:
        if randomize_on_each_loop:
            self.randomize_on_each_loop.select()
        else:
            self.randomize_on_each_loop.deselect()


def test_recorded_char_press_uses_time_relative_to_first_key_press():
    tuney = Tuney()

    actual = [
        tuney.recorded_char_press(CharPress('a', time=1_700_000_000.0)),
        tuney.recorded_char_press(CharPress('a', False, 1_700_000_000.25)),
        tuney.recorded_char_press(CharPress('b', time=1_700_000_001.0)),
    ]

    assert actual == [
        CharPress('a', time=0.0),
        CharPress('a', False, 250.0),
        CharPress('b', time=1000.0),
    ]


def test_recorded_char_press_reuses_deleted_time_for_next_insert():
    tuney = Tuney()
    assert tuney.recorded_char_press(CharPress('a', time=100.0)) == CharPress(
        'a', time=0.0
    )
    tuney._recording_insert_time = 0.0

    actual = [
        tuney.recorded_char_press(CharPress('b', time=110.0)),
        tuney.recorded_char_press(CharPress('b', False, 110.25)),
        tuney.recorded_char_press(CharPress('c', time=111.0)),
    ]

    assert actual == [
        CharPress('b', time=0.0),
        CharPress('b', False, 250.0),
        CharPress('c', time=1000.0),
    ]


def test_recorded_char_press_caps_silent_gap():
    tuney = Tuney(max_gap=0.5)
    for c in [
        CharPress('a', time=100.0),
        CharPress('a', False, 100.25),
    ]:
        tuney.char_presses.append(tuney.recorded_char_press(c))

    actual = [
        tuney.recorded_char_press(CharPress('b', time=110.0)),
        tuney.recorded_char_press(CharPress('b', False, 110.25)),
    ]

    assert actual == [
        CharPress('b', time=750.0),
        CharPress('b', False, 1000.0),
    ]


def test_recorded_char_press_does_not_cap_time_while_note_is_held():
    tuney = Tuney(max_gap=0.5)
    tuney.char_presses.append(tuney.recorded_char_press(CharPress('a', time=100.0)))

    actual = tuney.recorded_char_press(CharPress('b', time=110.0))

    assert actual == CharPress('b', time=10000.0)


def test_display_text_uses_only_key_presses():
    tuney = Tuney(
        text=[
            CharPress('a', time=0.0),
            CharPress('a', False, 250.0),
            CharPress('b', time=1000.0),
            CharPress('b', False, 1250.0),
        ]
    )

    assert tuney.display_text == 'ab'


def test_clear_resets_recording_state():
    tuney = Tuney(gui=True, text=[CharPress('a', time=0.0)])
    app = FakeApp()
    object.__setattr__(tuney, 'app', app)
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
    assert app.undo_count == 1


def test_randomize_timing_replaces_timing_and_keeps_display_text() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=100.0),
            CharPress('a', False, 200.0),
            CharPress('b', time=10_000.0),
            CharPress('b', False, 10_500.0),
        ],
    )
    app = FakeApp()
    object.__setattr__(tuney, 'app', app)
    original_char_presses = list(tuney.char_presses)
    tuney._recording_start_time = 100.0
    tuney._recording_time_offset = 20.0
    tuney._recording_insert_time = 10.0
    tuney._replay_text = 'a'

    tuney.randomize_timing()

    assert tuney.display_text == 'ab'
    assert tuney.char_presses != original_char_presses
    assert [c.char for c in tuney.char_presses if c.is_press] == ['a', 'b']
    assert tuney._recording_start_time is None
    assert tuney._recording_time_offset == 0.0
    assert tuney._recording_insert_time is None
    assert tuney._replay_text == ''
    assert app.undo_count == 1


def test_on_char_records_undo_for_added_char_press() -> None:
    tuney = Tuney(gui=True)
    app = FakeApp()
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('a', time=100.0))

    assert app.undo_count == 1


def test_backspace_autorepeat_starts_after_configured_delay() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
        ],
        backspace_repeat_delay=1.5,
        backspace_repeat_rate=4.0,
    )
    app = FakeApp()
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('\b', time=200.0))

    assert tuney.display_text == 'a'
    assert app.after_calls[0][1] == 1500


def test_backspace_autorepeat_repeats_at_configured_rate() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0.0),
            CharPress('b', time=100.0),
            CharPress('c', time=200.0),
        ],
        backspace_repeat_delay=2.0,
        backspace_repeat_rate=5.0,
    )
    app = FakeApp()
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('\b', time=300.0))
    first_callback = app.after_calls[0][2]
    assert callable(first_callback)
    first_callback()

    assert tuney.display_text == 'a'
    assert app.after_calls[1][1] == 200


def test_backspace_release_cancels_autorepeat() -> None:
    tuney = Tuney(gui=True, text=[CharPress('a', time=0.0)])
    app = FakeApp()
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('\b', time=100.0))
    tuney.on_char(CharPress('\b', False, time=200.0))

    assert app.cancelled_after_ids == ['after-0']
    assert tuney._backspace_repeat_after_id is None


def test_backspace_autorepeat_can_be_disabled() -> None:
    tuney = Tuney(
        gui=True,
        text=[CharPress('a', time=0.0)],
        backspace_repeat_rate=0,
    )
    app = FakeApp()
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('\b', time=100.0))

    assert app.after_calls == []


def test_restore_data_restores_char_presses_and_model_values() -> None:
    tuney = Tuney(max_gap=1.0, text=[CharPress('a', time=0)])

    tuney.restore_data({'max_gap': 2.0, 'text': [CharPress('b', time=0).model_dump()]})

    assert tuney.max_gap == 2.0
    assert tuney.char_presses == [CharPress('b', time=0)]


def test_app_undo_and_redo_restore_history_state() -> None:
    app = App.__new__(App)
    app.tuney = Tuney(max_gap=1.0)
    app.ui = FakeLayout()
    app._loop_replay = False
    app.loop_before = 0.0
    app.loop_after = 0.0
    app.loop_tempo = 1.0
    app.randomize_on_each_loop = False
    app._undo_stack = []
    app._redo_stack = []

    app.record_undo()
    object.__setattr__(app.tuney, 'max_gap', 2.0)
    app.loop_before = 0.5
    app.on_undo()

    assert app.tuney.max_gap == 1.0
    assert app.loop_before == 0.0

    app.on_redo()

    assert app.tuney.max_gap == 2.0
    assert app.loop_before == 0.5


def test_finished_replay_restarts_when_looping(monkeypatch) -> None:
    calls: list[str] = []
    tuney = Tuney(gui=True, text=[CharPress('a', time=0)])
    app = FakeApp()
    app.is_replaying = True
    app.loop_replay = True
    object.__setattr__(tuney, 'app', app)
    monkeypatch.setattr(Tuney, 'on_replay', lambda self: calls.append('replay'))

    tuney._finish_replay()

    assert calls == ['replay']
    assert app.is_replaying


def test_finished_empty_replay_stops_when_looping() -> None:
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.is_replaying = True
    app.loop_replay = True
    object.__setattr__(tuney, 'app', app)

    tuney._finish_replay()

    assert not app.is_replaying


def test_replay_char_presses_use_loop_tempo() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 1000),
        ],
    )
    app = FakeApp()
    app.loop_tempo = 2.0
    object.__setattr__(tuney, 'app', app)

    assert tuney._replay_char_presses() == [
        CharPress('a', time=0),
        CharPress('a', False, 500),
    ]


def test_replay_char_presses_cut_loop_start_and_end() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
            CharPress('b', time=1000),
            CharPress('b', False, 1500),
        ],
    )
    app = FakeApp()
    app.loop_before = 0.5
    app.loop_after = 0.25
    object.__setattr__(tuney, 'app', app)

    assert tuney._replay_char_presses() == [
        CharPress('a', False, 0),
        CharPress('b', time=500),
    ]


def test_replay_char_presses_add_loop_start_and_end_space() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
        ],
    )
    app = FakeApp()
    app.loop_before = -0.25
    app.loop_after = -0.75
    object.__setattr__(tuney, 'app', app)

    assert tuney._replay_char_presses() == [
        CharPress('a', time=250),
        CharPress('a', False, 750),
        CharPress(time=1500),
    ]


def test_loop_randomize_replaces_playback_timing_without_changing_recording() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
            CharPress('b', time=10_000),
            CharPress('b', False, 11_000),
            CharPress('c', time=20_000),
            CharPress('c', False, 21_000),
            CharPress('d', time=30_000),
            CharPress('d', False, 31_000),
        ],
        text_timings=TextTimings(seed=1, overlap=0, timings=[10, 20, 30]),
    )
    app = FakeApp()
    app.loop_replay = True
    app.randomize_on_each_loop = True
    object.__setattr__(tuney, 'app', app)
    recorded_char_presses = list(tuney.char_presses)

    first_loop = tuney._replay_char_presses()
    second_loop = tuney._replay_char_presses()

    assert tuney.char_presses == recorded_char_presses
    assert first_loop != recorded_char_presses
    assert second_loop != first_loop
    assert ''.join(c.char for c in first_loop if c.is_press) == 'abcd'
    assert ''.join(c.char for c in second_loop if c.is_press) == 'abcd'


def test_randomize_on_each_loop_only_affects_loop_replay() -> None:
    tuney = Tuney(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
        text_timings=TextTimings(seed=1, overlap=0, timings=[10, 20, 30]),
    )
    app = FakeApp()
    app.randomize_on_each_loop = True
    object.__setattr__(tuney, 'app', app)

    assert tuney._replay_char_presses() == tuney.char_presses


def test_on_char_ignores_input_while_saving():
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.is_saving = True
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('a', time=100.0))

    assert tuney.char_presses == []


def test_on_char_ignores_input_without_app_focus():
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.has_focus = False
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('a', time=100.0))

    assert tuney.char_presses == []


def test_on_char_ignores_input_with_control_panel_focus():
    tuney = Tuney(gui=True)
    app = FakeApp()
    app.focus_in_control_panel = True
    object.__setattr__(tuney, 'app', app)

    tuney.on_char(CharPress('a', time=100.0))

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
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )

    tuney()

    assert events == [(-6, True), (-6, False)]
    assert lifecycle == ['stop_all', 'wait', 'close']
    assert 'app' not in tuney.__dict__
    assert 'listener' not in tuney.__dict__


def test_cli_mode_prints_characters_as_they_play(
    monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(MultiPlayer, 'on_note', lambda *args: True)
    tuney = Tuney(
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
            CharPress('b', time=0),
            CharPress('b', False, 0),
        ],
    )

    tuney._play_cli()

    assert capsys.readouterr().out == 'ab\n'


def test_cli_mode_prints_newline_before_keyboard_interrupt(
    monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupt(*args: object) -> bool:
        raise KeyboardInterrupt

    monkeypatch.setattr(MultiPlayer, 'on_note', interrupt)
    tuney = Tuney(text=[CharPress('a', time=0)])

    with pytest.raises(KeyboardInterrupt):
        tuney._play_cli()

    assert capsys.readouterr().out == 'a\n'


def test_cli_mode_requires_text(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        Tuney()()

    error = capsys.readouterr().err
    assert exc_info.value.code == 2
    assert 'Required options were not provided: TEXT' in error
    assert 'For full helptext, run tuney --help' in error


def test_cli_mode_requires_sound() -> None:
    with pytest.raises(SystemExit, match='CLI mode requires sound'):
        Tuney(silent=True, text='a')()


def test_output_forces_cli_mode(tmp_path) -> None:
    tuney = Tuney(gui=True, output=tmp_path / 'out.wav')

    assert not tuney.gui


@pytest.mark.parametrize('suffix', ['wav', 'mp3', 'flac'])
def test_silent_cli_mode_writes_audio_file(tmp_path, suffix: str) -> None:
    path = tmp_path / f'out.{suffix}'
    tuney = Tuney(
        output=path,
        silent=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
    )

    tuney()
    audio, sample_rate = soundfile.read(path, always_2d=True)
    with soundfile.SoundFile(path) as file:
        metadata = tomllib.loads(file.copy_metadata()['comment'])
    settings = tomllib.loads(metadata['settings'])

    assert sample_rate == 48_000
    assert len(audio) >= 24_000
    assert audio.shape[1] == 1
    assert audio.any()
    assert metadata['original_text'] == 'a'
    assert datetime.fromisoformat(metadata['recording_start_time'])
    assert datetime.fromisoformat(metadata['recording_finish_time'])
    assert settings['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0},
        {'char': 'a', 'is_press': False, 'time': 100},
    ]


def test_live_cli_output_records_during_playback(monkeypatch, tmp_path) -> None:
    path = tmp_path / 'out.wav'
    lifecycle: list[object] = []
    monkeypatch.setattr(MultiPlayer, 'on_note', lambda *args: True)
    monkeypatch.setattr(
        MultiPlayer,
        'start_recording',
        lambda self, output, comment=None: lifecycle.append(
            ('start_recording', output, comment)
        ),
    )
    monkeypatch.setattr(
        MultiPlayer, 'stop_all', lambda self: lifecycle.append('stop_all')
    )
    monkeypatch.setattr(MultiPlayer, 'wait', lambda self: lifecycle.append('wait'))
    monkeypatch.setattr(
        MultiPlayer, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    monkeypatch.setattr(MultiPlayer, 'close', lambda self: lifecycle.append('close'))
    tuney = Tuney(
        output=path,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )

    tuney()

    start_recording, stop_all, wait, stop_recording, close = lifecycle
    assert start_recording[0] == 'start_recording'
    assert start_recording[1] == path
    assert callable(start_recording[2])
    assert [
        stop_all,
        wait,
        stop_recording,
        close,
    ] == [
        'stop_all',
        'wait',
        'stop_recording',
        'close',
    ]


def test_interrupted_output_removes_partial_file(monkeypatch, tmp_path) -> None:
    path = tmp_path / 'out.wav'

    def interrupt(self, output, events, comment=None) -> None:
        output.write_bytes(b'partial')
        raise KeyboardInterrupt

    monkeypatch.setattr(MultiPlayer, 'render_file', interrupt)
    tuney = Tuney(output=path, silent=True, text='a')

    with pytest.raises(KeyboardInterrupt):
        tuney()

    assert not path.exists()


def test_gui_transport_records_audio_until_save(monkeypatch, tmp_path) -> None:
    output = tmp_path / 'out.wav'
    lifecycle: list[object] = []

    def start_recording(
        self,
        path: Path,
        comment: object | None = None,
        append: bool = False,
    ) -> None:
        lifecycle.append(('start_recording', path, comment, append))

    monkeypatch.setattr(MultiPlayer, 'start_recording', start_recording)
    monkeypatch.setattr(
        MultiPlayer, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    tuney = Tuney(gui=True)

    assert tuney.on_transport_state(State.ready, State.recording, Action.record)
    comment = tuney._audio_recording_comment
    assert tuney.on_transport_state(State.recording, State.paused, Action.record)
    assert tuney.on_transport_state(State.paused, State.recording, Action.record)
    assert tuney.on_transport_state(State.recording, State.ready, Action.save, output)

    first_start, stop, second_start, stop_before_save = lifecycle
    assert first_start[0] == 'start_recording'
    assert first_start[2] is comment
    assert first_start[3] is False
    assert stop == 'stop_recording'
    assert second_start[0] == 'start_recording'
    assert second_start[1] == first_start[1]
    assert second_start[2] is comment
    assert second_start[3] is True
    assert stop_before_save == 'stop_recording'
    assert output.exists()
    assert tuney._audio_recording_path is None
    assert tuney._audio_recording_comment is None


def test_gui_transport_cancel_keeps_audio_recording(monkeypatch) -> None:
    lifecycle: list[object] = []
    monkeypatch.setattr(
        MultiPlayer,
        'start_recording',
        lambda self, path, comment=None, append=False: lifecycle.append(
            ('start_recording', path, comment, append)
        ),
    )
    monkeypatch.setattr(
        MultiPlayer, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    tuney = Tuney(gui=True)

    assert tuney.on_transport_state(State.ready, State.recording, Action.record)
    recording_path = tuney._audio_recording_path

    assert not tuney.on_transport_state(State.recording, State.ready, Action.save)
    assert tuney._audio_recording_path == recording_path
    assert lifecycle[0][0] == 'start_recording'
    assert lifecycle == [lifecycle[0]]
    if recording_path is not None:
        recording_path.unlink(missing_ok=True)


def test_gui_transport_clear_discards_audio_recording(monkeypatch) -> None:
    lifecycle: list[object] = []
    monkeypatch.setattr(
        MultiPlayer,
        'start_recording',
        lambda self, path, comment=None, append=False: lifecycle.append(
            ('start_recording', path, comment, append)
        ),
    )
    monkeypatch.setattr(
        MultiPlayer, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    tuney = Tuney(gui=True)

    assert tuney.on_transport_state(State.ready, State.recording, Action.record)
    recording_path = tuney._audio_recording_path
    assert recording_path is not None

    assert tuney.on_transport_state(State.recording, State.ready, Action.clear)

    assert lifecycle[0][0] == 'start_recording'
    assert lifecycle[1] == 'stop_recording'
    assert not recording_path.exists()
    assert tuney._audio_recording_path is None
    assert tuney._audio_recording_comment is None
