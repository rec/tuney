from collections.abc import Callable
from pathlib import Path

import mido
import pytest

from tuney.app.app import App
from tuney.app.key_recorder import speech_phrases
from tuney.audio.mixer import NotePress
from tuney.audio.player import Player
from tuney.audio.speech import SpeechPhrase
from tuney.midi import port
from tuney.midi.midi import Midi, MidiIn, MidiOut
from tuney.time.char_press import CharPress
from tuney.time.text_timings import TextTimings
from tuney.ui import main_window
from tuney.ui.main_window import MainWindow
from tuney.ui.state import Action, State

from .app_helpers import FakeApp, on_transport_state, temporary_path


def test_gui_start_uses_qt_keys_without_background_listener(monkeypatch) -> None:
    started = []
    app = App(gui=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    monkeypatch.setattr(app.keyboard_listener, 'start', lambda: started.append(True))

    app.start()

    assert started == []


def test_gui_start_uses_background_listener_when_enabled(monkeypatch) -> None:
    started = []
    app = App(gui=True, run_in_background=True)
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    monkeypatch.setattr(app.keyboard_listener, 'start', lambda: started.append(True))

    app.start()

    assert started == [True]


def test_gui_start_leaves_midi_device_monitor_stopped_when_midi_is_disabled() -> None:
    app = App(
        gui=True, midi=Midi(input=MidiIn(enable=False), output=MidiOut(enable=False))
    )
    main_window = FakeApp()
    main_window.app = app
    app.__dict__['main_window'] = main_window
    app.__dict__['midi_listener'] = type(
        'FakeMidiListener',
        (),
        {'start': lambda self: None},
    )()

    app.start()

    assert main_window.midi_device_monitor_start_count == 0


def test_gui_start_sends_midi_tuning_when_enabled(monkeypatch) -> None:
    messages = []

    class Port:
        def send(self, message: object) -> None:
            messages.append(message)

    app = App(gui=True, midi=Midi(output=MidiOut(enable=True, send_tuning=True)))
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    app.__dict__['midi_listener'] = type(
        'FakeMidiListener',
        (),
        {'start': lambda self: None},
    )()
    monkeypatch.setattr(port.mido, 'open_output', lambda *_args, **_kwargs: Port())

    app.start()

    assert [m.type for m in messages] == [
        'program_change',
        'control_change',
        'sysex',
    ]
    assert main_window.midi_device_monitor_start_count == 1


def test_midi_device_monitor_sync_follows_midi_enable_state() -> None:
    calls = []
    app = App(midi=Midi(input=MidiIn(enable=False), output=MidiOut(enable=False)))
    window = type(
        'Window',
        (),
        {
            'app': app,
            'start_midi_device_monitor': lambda self: calls.append('start'),
            '_stop_midi_device_monitor': lambda self: calls.append('stop'),
        },
    )()

    MainWindow.sync_midi_device_monitor(window)
    app.midi.output.enable = True
    MainWindow.sync_midi_device_monitor(window)
    app.midi.output.enable = False
    MainWindow.sync_midi_device_monitor(window)

    assert calls == ['stop', 'start', 'stop']


def test_gui_start_reports_midi_output_open_failure(monkeypatch) -> None:
    def open_output(*_: object, **__: object) -> object:
        raise SystemError('MidiOutWinMM::openPort: error creating port')

    app = App(gui=True, midi=Midi(output=MidiOut(enable=True)))
    main_window = FakeApp()
    app.__dict__['main_window'] = main_window
    app.__dict__['midi_listener'] = type(
        'FakeMidiListener',
        (),
        {'start': lambda self: None},
    )()
    monkeypatch.setattr(port.mido, 'open_output', open_output)

    app.start()

    assert not app.midi.output.enable
    assert main_window.__dict__['midi_output_errors'] == [
        'MidiOutWinMM::openPort: error creating port'
    ]
    assert main_window.midi_device_monitor_start_count == 1


def test_midi_device_change_clears_missing_selected_output(monkeypatch) -> None:
    messages = []

    class MessageBox:
        @staticmethod
        def information(_parent: object, _title: str, text: str) -> None:
            messages.append(text)

    class Ui:
        def __init__(self) -> None:
            self.refresh_count = 0

        def refresh_midi_devices(self) -> None:
            self.refresh_count += 1

    class Autosave:
        def __init__(self) -> None:
            self.save_count = 0

        def save(self, _callback: object) -> None:
            self.save_count += 1

    class Port:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    app = App(midi=Midi(output=MidiOut(name='Old Synth')))
    app.__dict__['_autosave'] = Autosave()
    app.__dict__['save_autosave'] = object()
    ui = Ui()
    window = type('Window', (), {'app': app, 'ui': ui})()
    port = Port()
    app.midi.output.__dict__['port'] = port
    monkeypatch.setattr(main_window.QtWidgets, 'QMessageBox', MessageBox)

    MainWindow._on_midi_devices_changed(window, [['keyboard'], ['New Synth']])

    assert app.midi.output.name is None
    assert port.close_count == 1
    assert ui.refresh_count == 2
    assert messages == ['Output device Old Synth no longer exists']
    assert app._autosave.save_count == 1


def test_finished_replay_restarts_when_looping(monkeypatch) -> None:
    calls: list[str] = []
    app = App(gui=True, text=[CharPress('a', time=0)])
    main_window = FakeApp()
    main_window.is_replaying = True
    main_window.loop_replay = True
    app.__dict__['main_window'] = main_window
    monkeypatch.setattr(App, 'on_replay', lambda _: calls.append('replay'))

    app.key_recorder.finish_replay(app)

    assert calls == ['replay']
    assert main_window.is_replaying


def test_stale_finished_replay_does_not_restart_when_stopped(monkeypatch) -> None:
    calls: list[str] = []
    app = App(gui=True, text=[CharPress('a', time=0)])
    main_window = FakeApp()
    main_window.is_replaying = False
    main_window.loop_replay = True
    app.__dict__['main_window'] = main_window
    monkeypatch.setattr(App, 'on_replay', lambda _: calls.append('replay'))

    app.key_recorder.finish_replay(app)

    assert calls == []
    assert not main_window.is_replaying


def test_finished_empty_replay_stops_when_looping() -> None:
    app = App(gui=True)
    main_window = FakeApp()
    main_window.is_replaying = True
    main_window.loop_replay = True
    app.__dict__['main_window'] = main_window

    app.key_recorder.finish_replay(app)

    assert not main_window.is_replaying


def test_replay_moves_cursor_as_text_is_played(monkeypatch) -> None:
    class FakePlayer:
        @staticmethod
        def stop_all() -> None:
            pass

    class FakeSequencer:
        def __init__(
            self,
            char_presses: list[CharPress],
            callback: Callable[[CharPress | None], object],
        ) -> None:
            self.char_presses = char_presses
            self.callback = callback

        def start(self) -> None:
            for c in self.char_presses:
                self.callback(c)

        @staticmethod
        def stop() -> None:
            pass

    class FakeUi:
        def __init__(self) -> None:
            self.text: list[str] = []
            self.cursor: list[int | None] = []

        def set_text(self, text: str) -> None:
            self.text.append(text)

        def set_play_cursor(self, index: int | None) -> None:
            self.cursor.append(index)

        @staticmethod
        def start_loop_clock() -> None:
            pass

    class FakeReplayWindow(FakeApp):
        def after(self, delay: int, callback: object, *args: object) -> str:
            assert delay == 0
            assert callable(callback)
            callback(*args)
            return 'after-0'

    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
            CharPress('b', time=200),
        ],
    )
    main_window = FakeReplayWindow()
    main_window.is_replaying = True
    main_window.ui = FakeUi()
    app.__dict__['main_window'] = main_window
    app.__dict__['player'] = FakePlayer()
    monkeypatch.setattr('tuney.app.key_recorder.Sequencer', FakeSequencer)
    monkeypatch.setattr(App, 'play_char', lambda *_: None)

    app.key_recorder.on_replay(app)

    assert main_window.ui.text == ['', 'a', 'ab']
    assert main_window.ui.cursor == [0, 1, 2]


def test_replay_starts_speech(monkeypatch) -> None:
    class FakePlayer:
        def __init__(self) -> None:
            self.speech: list[tuple[list[SpeechPhrase], float, float, str | None]] = []

        @staticmethod
        def stop_all() -> None:
            pass

        def start_speech(
            self,
            phrases: list[SpeechPhrase],
            level: float,
            speed: float,
            voice: str | None,
        ) -> None:
            self.speech.append((phrases, level, speed, voice))

    class FakeSequencer:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        @staticmethod
        def start() -> None:
            pass

    app = App(
        gui=True,
        use_speech=True,
        speech_level=0.5,
        speech_voice='Alex',
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
            CharPress('b', time=200),
            CharPress('b', False, 400),
        ],
    )
    main_window = FakeApp()
    main_window.is_replaying = True
    app.__dict__['main_window'] = main_window
    player = FakePlayer()
    app.__dict__['player'] = player
    monkeypatch.setattr('tuney.app.key_recorder.Sequencer', FakeSequencer)

    app.key_recorder.on_replay(app)

    assert player.speech == [([SpeechPhrase(text='ab', start=0.0)], 0.5, 0.8, 'Alex')]


def test_speech_phrases_split_on_punctuation_and_align_to_note_starts() -> None:
    assert speech_phrases(
        [
            CharPress(' ', time=0),
            CharPress('H', time=100),
            CharPress('i', time=200),
            CharPress('!', time=300),
            CharPress('!', False, 350),
            CharPress(' ', time=400),
            CharPress('B', time=500),
            CharPress('y', time=600),
            CharPress('e', time=700),
        ]
    ) == [
        SpeechPhrase(text='Hi!', start=0.1),
        SpeechPhrase(text='Bye', start=0.5),
    ]


def test_speech_phrases_can_render_whole_text_as_one_phrase() -> None:
    assert speech_phrases(
        [
            CharPress(' ', time=0),
            CharPress('H', time=100),
            CharPress('i', time=200),
            CharPress('!', time=300),
            CharPress(' ', time=400),
            CharPress('B', time=500),
            CharPress('y', time=600),
            CharPress('e', time=700),
        ],
        False,
    ) == [SpeechPhrase(text='Hi! Bye', start=0.1)]


def test_replay_char_presses_use_loop_tempo() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 1000),
        ],
    )
    main_window = FakeApp()
    main_window.loop_tempo = 2.0
    app.__dict__['main_window'] = main_window

    assert app.replay_char_presses() == [
        CharPress('a', time=0),
        CharPress('a', False, 500),
    ]


def test_replay_char_presses_cut_loop_start_and_end() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
            CharPress('b', time=1000),
            CharPress('b', False, 1500),
        ],
    )
    main_window = FakeApp()
    main_window.loop_before = 0.5
    main_window.loop_after = 0.25
    app.__dict__['main_window'] = main_window

    assert app.replay_char_presses() == [
        CharPress('a', False, 0),
        CharPress('b', time=500),
    ]


def test_replay_char_presses_add_loop_start_and_end_space() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 500),
        ],
    )
    main_window = FakeApp()
    main_window.loop_before = -0.25
    main_window.loop_after = -0.75
    app.__dict__['main_window'] = main_window

    assert app.replay_char_presses() == [
        CharPress('a', time=250),
        CharPress('a', False, 750),
        CharPress(time=1500),
    ]


def test_loop_randomize_replaces_playback_timing_without_changing_recording() -> None:
    app = App(
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
    main_window = FakeApp()
    main_window.loop_replay = True
    main_window.randomize_on_each_loop = True
    app.__dict__['main_window'] = main_window
    recorded_char_presses = list(app.char_presses)

    first_loop = app.replay_char_presses()
    second_loop = app.replay_char_presses()

    assert app.char_presses == recorded_char_presses
    assert first_loop != recorded_char_presses
    assert second_loop != first_loop
    assert ''.join(c.char for c in first_loop if c.is_press) == 'abcd'
    assert ''.join(c.char for c in second_loop if c.is_press) == 'abcd'


def test_randomize_on_each_loop_only_affects_loop_replay() -> None:
    app = App(
        gui=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
        text_timings=TextTimings(seed=1, overlap=0, timings=[10, 20, 30]),
    )
    main_window = FakeApp()
    main_window.randomize_on_each_loop = True
    app.__dict__['main_window'] = main_window

    assert app.replay_char_presses() == app.char_presses


def test_on_char_ignores_input_while_saving():
    app = App(gui=True)
    main_window = FakeApp()
    main_window.is_saving = True
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('a', time=100.0))

    assert app.char_presses == []


def test_on_char_ignores_input_without_app_focus():
    app = App(gui=True)
    main_window = FakeApp()
    main_window.has_focus = False
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('a', time=100.0))

    assert app.char_presses == []


def test_on_char_ignores_input_with_control_panel_focus():
    app = App(gui=True)
    main_window = FakeApp()
    main_window.focus_in_control_panel = True
    app.__dict__['main_window'] = main_window

    app.on_char(CharPress('a', time=100.0))

    assert app.char_presses == []


def test_cli_mode_plays_recorded_events_without_gui(monkeypatch) -> None:
    events: list[tuple[int, bool]] = []
    lifecycle: list[str] = []
    monkeypatch.setattr(
        Player,
        'on_note',
        lambda self, note, is_press: events.append((note, is_press)) or True,
    )
    monkeypatch.setattr(Player, 'stop_all', lambda self: lifecycle.append('stop_all'))
    monkeypatch.setattr(Player, 'wait', lambda self: lifecycle.append('wait'))
    monkeypatch.setattr(Player, 'close', lambda self: lifecycle.append('close'))
    app = App(
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )

    app.run()

    assert events == [(20, True), (20, False)]
    assert lifecycle == ['stop_all', 'wait', 'close']
    assert 'main_window' not in app.__dict__
    assert 'listener' not in app.__dict__


def test_midi_output_mutes_audio_by_default(monkeypatch) -> None:
    events: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        MidiOut, 'send_note', lambda _, note, is_press: events.append((note, is_press))
    )
    monkeypatch.setattr(
        Player, 'on_note', lambda *_: pytest.fail('audio should be muted')
    )
    app = App(
        midi=Midi(output=MidiOut(enable=True)),
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )

    app.play_cli()

    assert events == [(20, True), (20, False)]


def test_midi_output_can_leave_audio_enabled(monkeypatch) -> None:
    audio_events: list[tuple[int, bool]] = []
    midi_events: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        Player,
        'on_note',
        lambda _, note, is_press: audio_events.append((note, is_press)) or True,
    )
    monkeypatch.setattr(
        MidiOut,
        'send_note',
        lambda _, note, is_press: midi_events.append((note, is_press)),
    )
    app = App(
        midi=Midi(output=MidiOut(enable=True, mute_audio_when_midi_enabled=False)),
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )

    app.play_cli()

    assert audio_events == [(20, True), (20, False)]
    assert midi_events == [(20, True), (20, False)]


def test_on_char_does_not_release_unplayed_opposite_case_midi_note(monkeypatch) -> None:
    midi_events: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        MidiOut,
        'send_note',
        lambda _, note, is_press: midi_events.append((note, is_press)),
    )
    app = App(gui=True, silent=True, midi=Midi(output=MidiOut(enable=True)))
    app.__dict__['main_window'] = FakeApp()

    app.on_char(CharPress('a', time=100.0))
    app.on_char(CharPress('a', False, time=100.25))

    assert midi_events == [(20, True), (20, False)]


def test_on_char_releases_pressed_case_when_shift_released_first(monkeypatch) -> None:
    midi_events: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        MidiOut,
        'send_note',
        lambda _, note, is_press: midi_events.append((note, is_press)),
    )
    app = App(gui=True, silent=True, midi=Midi(output=MidiOut(enable=True)))
    app.__dict__['main_window'] = FakeApp()

    app.on_char(CharPress('A', time=100.0))
    app.on_char(CharPress('a', False, time=100.25).with_pressed_char('A'))

    assert [(c.char, c.is_press) for c in app.char_presses] == [
        ('A', True),
        ('A', False),
    ]
    assert midi_events == [(-6, True), (-6, False)]


def test_cli_mode_prints_characters_as_they_play(
    monkeypatch,
) -> None:
    printed: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(Player, 'on_note', lambda *args: True)
    monkeypatch.setattr(
        'builtins.print',
        lambda *args, **kwargs: printed.append((args, kwargs)),
    )
    app = App(
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
            CharPress('b', time=0),
            CharPress('b', False, 0),
        ],
    )

    app.play_cli()

    assert printed == [
        (('a',), {'end': '', 'flush': True}),
        (('b',), {'end': '', 'flush': True}),
        ((), {}),
    ]


def test_cli_mode_prints_newline_before_keyboard_interrupt(
    monkeypatch,
) -> None:
    def interrupt(*args: object) -> bool:
        raise KeyboardInterrupt

    printed: list[tuple[tuple[object, ...], dict[str, object]]] = []
    interrupted = False
    monkeypatch.setattr(
        'builtins.print',
        lambda *args, **kwargs: printed.append((args, kwargs)),
    )
    monkeypatch.setattr(Player, 'on_note', interrupt)
    app = App(text=[CharPress('a', time=0)])
    try:
        app.play_cli()
    except KeyboardInterrupt:
        interrupted = True

    assert interrupted
    assert printed == [
        (('a',), {'end': '', 'flush': True}),
        ((), {}),
    ]


def test_cli_mode_requires_text() -> None:
    with pytest.raises(SystemExit) as exc_info:
        App().run()

    assert exc_info.value.code == 2


def test_cli_mode_requires_sound() -> None:
    with pytest.raises(SystemExit, match='CLI mode requires sound'):
        App(silent=True, text='a').run()


def test_silent_cli_can_play_midi_without_opening_audio(monkeypatch) -> None:
    app = App(silent=True, text=[CharPress('a'), CharPress('a', False)])
    app.midi.output.enable = True
    sent: list[bool] = []
    monkeypatch.setattr(
        type(app.midi.output),
        'send_note',
        lambda self, note, is_press: sent.append(is_press),
    )
    monkeypatch.setattr(
        Player, 'on_note', lambda *args: pytest.fail('audio was opened')
    )
    app.run_cli()
    assert sent == [True, False]
    assert 'player' not in app.__dict__


def test_output_forces_cli_mode() -> None:
    app = App(gui=True, output=Path('out.wav'))

    assert not app.gui


def test_silent_cli_mode_writes_audio_file(monkeypatch, tmp_path) -> None:
    path = tmp_path / 'out.wav'
    rendered: list[
        tuple[Path, list[tuple[int, NotePress]], Callable[[], str] | None]
    ] = []

    def render_file(
        self: Player,
        output: Path,
        events: list[tuple[int, NotePress]],
        comment: Callable[[], str] | None,
        speech: object,
    ) -> None:
        rendered.append((output, events, comment))

    monkeypatch.setattr(Player, 'render_file', render_file)
    app = App(
        output=path,
        silent=True,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ],
    )

    app.run()
    output, events, comment = rendered[0]

    assert output != path
    assert output.parent == path.parent
    assert output.suffix == path.suffix
    assert app.player.tuning == app.tuning
    assert [(frame, note.is_press) for frame, note in events] == [
        (0, True),
        (4800, False),
    ]
    assert callable(comment)


def test_text_file_output_writes_midi_file_without_audio(monkeypatch, tmp_path) -> None:
    def audio_call(*_: object) -> None:
        raise AssertionError('MIDI file output should not use audio')

    monkeypatch.setattr(Player, 'render_file', audio_call)
    monkeypatch.setattr(Player, 'stop_all', audio_call)
    text = tmp_path / 'input.txt'
    text.write_text('a')
    path = tmp_path / 'out.smf'
    app = App(
        output=path,
        text_file=text,
        text_timings=TextTimings(seed=1, overlap=0, timings=[100]),
    )

    app.run()

    file = mido.MidiFile(path)
    messages = [
        message for track in file.tracks for message in track if not message.is_meta
    ]

    assert file.ticks_per_beat == 1000
    assert messages[0].type == 'program_change'
    assert messages[0].time == 0
    assert messages[0].program == app.midi.output.program
    assert messages[1].type == 'control_change'
    assert messages[1].time == 0
    assert messages[1].control == 7
    assert messages[1].value == app.midi.output.volume
    assert [(i.type, i.time, i.note, i.velocity) for i in messages[2:]] == [
        ('note_on', 0, app.midi.output.midi_note(app.mapper('a')), 64),
        ('note_on', 100, app.midi.output.midi_note(app.mapper('a')), 0),
    ]


def test_live_cli_output_records_during_playback(monkeypatch, tmp_path) -> None:
    path = tmp_path / 'out.wav'
    lifecycle: list[object] = []
    monkeypatch.setattr(Player, 'on_note', lambda *args: True)
    monkeypatch.setattr(
        Player,
        'start_recording',
        lambda self, output, comment=None: lifecycle.append(
            ('start_recording', output, comment)
        ),
    )
    monkeypatch.setattr(Player, 'stop_all', lambda self: lifecycle.append('stop_all'))
    monkeypatch.setattr(Player, 'wait', lambda self: lifecycle.append('wait'))
    monkeypatch.setattr(
        Player,
        'stop_recording',
        lambda self: lifecycle.append('stop_recording'),
    )
    monkeypatch.setattr(Player, 'close', lambda self: lifecycle.append('close'))
    monkeypatch.setattr(App, 'play_cli', lambda self: lifecycle.append('play_cli'))
    app = App(
        output=path,
        text=[
            CharPress('a', time=0),
            CharPress('a', False, 0),
        ],
    )
    app.run()

    start_recording, play_cli, stop_all, wait, stop_recording, close = lifecycle
    assert start_recording[0] == 'start_recording'
    assert start_recording[1] != path
    assert start_recording[1].parent == path.parent
    assert start_recording[1].suffix == path.suffix
    assert callable(start_recording[2])
    assert [
        play_cli,
        stop_all,
        wait,
        stop_recording,
        close,
    ] == [
        'play_cli',
        'stop_all',
        'wait',
        'stop_recording',
        'close',
    ]


def test_interrupted_output_removes_partial_file(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'out.wav'

        def interrupt(
            self: Player,
            output: Path,
            events: list[tuple[int, NotePress]],
            comment: Callable[[], str] | None,
            speech: object,
        ) -> None:
            output.write_bytes(b'partial')
            raise KeyboardInterrupt

        monkeypatch.setattr(Player, 'render_file', interrupt)
        app = App(output=path, silent=True, text='a')

        with pytest.raises(KeyboardInterrupt):
            app.run()

        assert not path.exists()


def test_gui_transport_records_audio_until_save(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        output = tmp_path / 'out.wav'
        lifecycle: list[object] = []

        def start_recording(
            self,
            path: Path,
            comment: object | None = None,
            append: bool = False,
        ) -> None:
            lifecycle.append(('start_recording', path, comment, append))

        monkeypatch.setattr(Player, 'start_recording', start_recording)
        monkeypatch.setattr(
            Player,
            'stop_recording',
            lambda self: lifecycle.append('stop_recording'),
        )
        app = App(gui=True)
        assert on_transport_state(app, State.ready, State.recording, Action.record)
        comment = app.audio_recorder.comment
        assert on_transport_state(app, State.recording, State.paused, Action.record)
        assert on_transport_state(app, State.paused, State.recording, Action.record)
        assert on_transport_state(
            app, State.recording, State.ready, Action.save, output
        )

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
        assert app.audio_recorder.path is None
        assert app.audio_recorder.comment is None


def test_gui_transport_cancel_keeps_audio_recording(monkeypatch) -> None:
    lifecycle: list[object] = []
    monkeypatch.setattr(
        Player,
        'start_recording',
        lambda self, path, comment=None, append=False: lifecycle.append(
            ('start_recording', path, comment, append)
        ),
    )
    monkeypatch.setattr(
        Player, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    app = App(gui=True)

    assert on_transport_state(app, State.ready, State.recording, Action.record)
    recording_path = app.audio_recorder.path

    assert not on_transport_state(app, State.recording, State.ready, Action.save)
    assert app.audio_recorder.path == recording_path
    assert lifecycle[0][0] == 'start_recording'
    assert lifecycle == [lifecycle[0]]
    if recording_path is not None:
        recording_path.unlink(missing_ok=True)


def test_gui_transport_clear_discards_audio_recording(monkeypatch) -> None:
    lifecycle: list[object] = []
    monkeypatch.setattr(
        Player,
        'start_recording',
        lambda self, path, comment=None, append=False: lifecycle.append(
            ('start_recording', path, comment, append)
        ),
    )
    monkeypatch.setattr(
        Player, 'stop_recording', lambda self: lifecycle.append('stop_recording')
    )
    app = App(gui=True)

    assert on_transport_state(app, State.ready, State.recording, Action.record)
    recording_path = app.audio_recorder.path
    assert recording_path is not None

    assert on_transport_state(app, State.recording, State.ready, Action.clear)

    assert lifecycle[0][0] == 'start_recording'
    assert lifecycle[1] == 'stop_recording'
    assert not recording_path.exists()
    assert app.audio_recorder.path is None
    assert app.audio_recorder.comment is None
