from collections.abc import Callable, Iterator
from pathlib import Path
from queue import Queue
from threading import Event

import mido
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from tuney.app.app import App
from tuney.app.input_queue import INPUT_EVENTS_PER_TICK, InputQueue
from tuney.app.key_recorder import KeyRecorder, speech_phrases
from tuney.audio.mixer import NotePress
from tuney.audio.player import Player
from tuney.audio.speech import SpeechPhrase, SpeechRequest
from tuney.keyboard.listener import KeyboardListener
from tuney.midi import port
from tuney.midi.listener import MidiListener
from tuney.midi.midi import Midi, MidiIn, MidiOut
from tuney.time.char_press import CharPress
from tuney.time.text_timings import TextTimings
from tuney.ui import key_events, main_window
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


def test_midi_input_retries_when_device_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []
    opened = object()

    def open_input(self: port.InputPort, callback: object) -> object:
        attempts.append(self.name or '')
        if len(attempts) == 1:
            raise OSError('device unavailable')
        return opened

    monkeypatch.setattr(port.InputPort, '__call__', open_input)
    monkeypatch.setattr('tuney.midi.listener.report_error', lambda message: None)
    app = App(midi=Midi(input=MidiIn(enable=True, name='keyboard')))
    listener = MidiListener(app.midi, lambda note, is_press: None)
    app.__dict__['midi_listener'] = listener
    window = type(
        'Window',
        (),
        {
            'app': app,
            'ui': type('UI', (), {'refresh_midi_devices': lambda self: None})(),
        },
    )()

    listener.start()
    assert listener.port is None
    MainWindow._on_midi_devices_changed(window, [[], []])
    assert attempts == ['keyboard']
    MainWindow._on_midi_devices_changed(window, [['keyboard'], []])
    assert listener.port is opened
    assert attempts == ['keyboard', 'keyboard']


def test_midi_monitor_preserves_names_on_probe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Names:
        names = [['keyboard'], ['synth']]

        def __call__(self) -> list[list[str]]:
            return self.names

        def replace(self, names: list[list[str]]) -> None:
            self.names = names

    class Stop:
        waits = 0

        @staticmethod
        def is_set() -> bool:
            return False

        def wait(self, timeout: float) -> bool:
            assert timeout == 2
            self.waits += 1
            return self.waits == 2

    probes: list[list[list[str] | None]] = [[None, None], [[], []]]
    names = Names()
    queue = Queue[list[list[str]]](maxsize=1)
    queue.put([['stale input'], ['stale output']])
    window = type(
        'Window',
        (),
        {'_midi_device_stop': Stop(), 'midi_device_queue': queue},
    )()

    def probe() -> list[list[str] | None]:
        if len(probes) == 1:
            assert names.names == [['keyboard'], ['synth']]
            assert queue.qsize() == 1
        return probes.pop(0)

    monkeypatch.setattr(main_window, 'midi_names', names)
    monkeypatch.setattr(main_window, 'probe_midi_names', probe)

    MainWindow._watch_midi_devices(window, window._midi_device_stop)

    assert names.names == [[], []]
    assert queue.get_nowait() == [[], []]
    assert queue.empty()


def test_midi_monitor_restart_keeps_stopped_worker_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Thread:
        @staticmethod
        def join(timeout: float) -> None:
            assert timeout == 1

    old_stop = Event()
    window = type(
        'Window',
        (),
        {
            '_midi_device_stop': old_stop,
            '_midi_device_thread': Thread(),
            '_watch_midi_devices': lambda self, stop: None,
        },
    )()
    monkeypatch.setattr(main_window, 'start_thread', lambda _target: Thread())

    MainWindow._stop_midi_device_monitor(window)
    MainWindow.start_midi_device_monitor(window)

    assert old_stop.is_set()
    assert window._midi_device_stop is not old_stop
    assert not window._midi_device_stop.is_set()


def test_midi_monitor_does_not_publish_probe_after_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Names:
        names = [['keyboard'], ['synth']]

        def __call__(self) -> list[list[str]]:
            return self.names

        def replace(self, names: list[list[str]]) -> None:
            self.names = names

    stop = Event()
    names = Names()
    queue = Queue[list[list[str]]]()
    window = type('Window', (), {'midi_device_queue': queue})()

    def probe() -> list[list[str] | None]:
        stop.set()
        return [[], []]

    monkeypatch.setattr(main_window, 'midi_names', names)
    monkeypatch.setattr(main_window, 'probe_midi_names', probe)

    MainWindow._watch_midi_devices(window, stop)

    assert names.names == [['keyboard'], ['synth']]
    assert queue.empty()


def test_gui_input_burst_bounds_work_and_preserves_release() -> None:
    class IdlePlayer:
        pass

    class Listener:
        @staticmethod
        def dispatch_pending(limit: int) -> None:
            assert limit == INPUT_EVENTS_PER_TICK

    class Application:
        midi_listener = Listener()
        player = IdlePlayer()
        received: list[CharPress] = []

        def on_char(self, c: CharPress) -> None:
            self.received.append(c)

    class Window:
        app = Application()
        key_queue = InputQueue[CharPress](256, lambda c: c.is_press, lambda c: c.char)
        queue = InputQueue[CharPress](256, lambda c: c.is_press, lambda c: c.char)
        midi_device_queue = Queue[list[list[str]]](maxsize=1)
        visual: list[CharPress] = []

        def _on_char(self, c: CharPress) -> None:
            self.visual.append(c)

        @staticmethod
        def _on_midi_devices_changed(_names: list[list[str]]) -> None:
            pass

    window = Window()
    for i in range(300):
        MainWindow.on_key(window, CharPress('a', time=i))
        MainWindow.on_char(window, CharPress('a', time=i))
    MainWindow.on_key(window, CharPress('a', False, time=301))
    MainWindow.on_char(window, CharPress('a', False, time=301))

    assert len(window.key_queue) == len(window.queue) == 256
    MainWindow._handle_queue(window)
    assert len(window.app.received) == len(window.visual) == INPUT_EVENTS_PER_TICK
    for _ in range(8):
        MainWindow._handle_queue(window)
    assert len(window.app.received) == len(window.visual) == 256
    assert not window.app.received[-1].is_press
    assert not window.visual[-1].is_press


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


def test_replay_dispatches_playback_to_gui_and_ignores_stopped_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            self.callback(self.char_presses[0])

        @staticmethod
        def stop() -> None:
            pass

    press = CharPress('a', time=0)
    app = App(gui=True, text=[press])
    window = FakeApp()
    window.is_replaying = True
    app.__dict__['main_window'] = window
    app.__dict__['player'] = FakePlayer()
    played: list[CharPress] = []
    monkeypatch.setattr('tuney.app.key_recorder.Sequencer', FakeSequencer)
    monkeypatch.setattr(App, 'play_char', lambda _, c: played.append(c))

    app.key_recorder.on_replay(app)

    assert played == []
    assert len(window.after_calls) == 1
    _, _, old_deliver, old_args = window.after_calls[0]
    assert callable(old_deliver)

    app.key_recorder.on_replay(app)
    old_deliver(*old_args)
    assert played == []
    _, _, deliver, args = window.after_calls[1]
    assert callable(deliver)
    deliver(*args)
    assert played == [press]

    window.is_replaying = False
    app.key_recorder.on_replay(app)
    deliver(*args)
    assert played == [press]


def test_shutdown_closes_remaining_resources_after_midi_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    errors: list[str] = []

    class Resource:
        def __init__(self, name: str, fail: bool = False) -> None:
            self.name = name
            self.fail = fail

        def close(self) -> None:
            calls.append(self.name)
            if self.fail:
                raise OSError('device removed')

        def stop(self) -> None:
            calls.append(self.name)

        def stop_all(self) -> None:
            calls.append('stop audio')

        def wait(self, timeout: float) -> None:
            assert timeout == 2.0
            calls.append('wait for audio')

    class Autosave:
        @staticmethod
        def save(_callback: object) -> None:
            pass

    class ControlPanel:
        @staticmethod
        def save_state() -> None:
            pass

    class AppState:
        _autosave = Autosave()
        midi_listener = Resource('MIDI input', fail=True)
        midi = type('Midi', (), {'output': Resource('MIDI output')})()
        player = Resource('audio')

        @staticmethod
        def save_autosave(_path: object) -> None:
            pass

    app = AppState()
    app.__dict__['keyboard_listener'] = Resource('keyboard')
    window = type(
        'Window',
        (),
        {'app': app, 'ui': type('Ui', (), {'control_panel': ControlPanel()})()},
    )()
    monkeypatch.setattr(main_window, 'report_error', errors.append)

    MainWindow._close_app(window)

    assert calls == [
        'keyboard',
        'MIDI input',
        'MIDI output',
        'stop audio',
        'wait for audio',
        'audio',
    ]
    assert window._shutdown_failed
    assert errors == ['Could not close MIDI input during shutdown: device removed']


def test_replay_starts_speech(monkeypatch) -> None:
    class FakePlayer:
        def __init__(self) -> None:
            self.speech: list[tuple[list[SpeechPhrase], float, float, str | None]] = []
            self.prepared_speech = self

        @staticmethod
        def stop_all() -> None:
            pass

        def speech_request(
            self,
            phrases: list[SpeechPhrase],
            level: float,
            speed: float,
            voice: str | None,
        ) -> SpeechRequest:
            self.speech.append((phrases, level, speed, voice))
            return SpeechRequest(
                phrases=phrases,
                sample_rate=48_000,
                level=level,
                speed=speed,
                voice=voice,
            )

        @staticmethod
        def take(_request: SpeechRequest) -> None:
            return None

        @staticmethod
        def play_speech(_speech: object) -> None:
            pass

    class FakeSequencer:
        started = 0

        def __init__(self, *_: object, **__: object) -> None:
            pass

        def start(self) -> None:
            type(self).started += 1

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
    jobs = []
    monkeypatch.setattr('tuney.app.key_recorder.start_thread', jobs.append)
    monkeypatch.setattr('tuney.app.key_recorder.render_speech', lambda _: None)

    app.key_recorder.on_replay(app)

    assert player.speech == [([SpeechPhrase(text='ab', start=0.0)], 0.5, 0.8, 'Alex')]
    assert len(jobs) == 1
    assert FakeSequencer.started == 0
    jobs.pop()()
    _, _, callback, args = main_window.after_calls.pop()
    callback(*args)
    assert FakeSequencer.started == 1


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


def test_focus_loss_releases_local_key_without_suppressing_global_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    midi_events: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        MidiOut,
        'send_note',
        lambda _, note, is_press: midi_events.append((note, is_press)),
    )
    app = App(gui=True, silent=True, midi=Midi(output=MidiOut(enable=True)))
    window = FakeApp()
    window.app = app
    window._key_chars = {Qt.Key.Key_A: 'a'}
    app.__dict__['main_window'] = window
    global_events: list[CharPress] = []
    listener = KeyboardListener(global_events.append)
    key = type('Key', (), {'char': 'a'})()

    app.on_char(CharPress('a', time=100.0))
    listener._on(key, True)
    window.has_focus = False
    key_events.release_held_keys(window)
    listener._on(key, False)
    key_events.on_key_event(
        window,
        QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_A, Qt.NoModifier),
        False,
    )

    assert [(c.char, c.is_press) for c in app.char_presses] == [
        ('a', True),
        ('a', False),
    ]
    assert midi_events == [(20, True), (20, False)]
    assert [c.is_press for c in global_events] == [True, False]
    assert window._key_chars == {}


def test_held_note_checks_scan_only_new_recording_events() -> None:
    class CountingPresses(list[CharPress]):
        scanned = 0

        def __iter__(self) -> Iterator[CharPress]:
            for c in super().__iter__():
                self.scanned += 1
                yield c

        def __getitem__(self, index: int | slice) -> CharPress | list[CharPress]:
            value = super().__getitem__(index)
            if isinstance(index, slice):
                self.scanned += len(value)
            return value

    recorder = KeyRecorder()
    presses = CountingPresses()
    for i in range(5_000):
        press = CharPress('a', i % 2 == 0, time=i / 1000)
        recorder.recorded_char_press(press, presses, 1.0)
        presses.append(press)

    assert presses.scanned <= 5_000
    assert recorder.recorded_notes_on(presses) == set()


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


def test_cli_interrupt_bounds_audio_cleanup_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[float | None] = []

    def interrupt(_app: App) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(App, 'play_cli', interrupt)
    monkeypatch.setattr(Player, 'stop_all', lambda *_: None)
    monkeypatch.setattr(Player, 'wait', lambda _, timeout: waits.append(timeout))
    monkeypatch.setattr(Player, 'close', lambda *_: None)

    with pytest.raises(KeyboardInterrupt):
        App(text='a').run_cli()

    assert waits == [5.0]


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
