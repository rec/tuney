import os
import signal
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from tuney.time.char_press import CharPress
from tuney.tuney import Tuney
from tuney.ui import main_window as main_window_module
from tuney.ui.history import History
from tuney.ui.main_window import SIGNAL_POLL_IN_MS, MainWindow


def test_qt_key_events() -> None:
    def key_event(
        key: Qt.Key,
        text: str = '',
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
        event_type: QKeyEvent.Type = QKeyEvent.Type.KeyPress,
    ) -> QKeyEvent:
        return QKeyEvent(event_type, key, modifiers, text)

    chars = []
    app = type('KeyApp', (), {})()
    app._key_chars = {}
    app.tuney = type('Tuney', (), {})()
    app.tuney.state = type('TuneyState', (), {'on_char': chars.append})()
    main_window_module.time.time = iter([100.0, 100.25, 100.5, 100.75]).__next__

    assert not MainWindow._on_key_event(app, key_event(Qt.Key.Key_CapsLock), True)
    assert not MainWindow._on_key_event(
        app, key_event(Qt.Key.Key_A, 'a', Qt.KeyboardModifier.MetaModifier), True
    )

    MainWindow._on_key_event(app, key_event(Qt.Key.Key_A, 'A'), True)
    MainWindow._on_key_event(
        app, key_event(Qt.Key.Key_A, event_type=QKeyEvent.Type.KeyRelease), False
    )
    MainWindow._on_key_event(app, key_event(Qt.Key.Key_Backspace), True)
    MainWindow._on_key_event(app, key_event(Qt.Key.Key_Return), True)

    assert chars == [
        CharPress('A', time=100.0),
        CharPress('A', False, time=100.25),
        CharPress('\b', time=100.5),
        CharPress('\n', time=100.75),
    ]


def test_app_event_filter() -> None:
    def key_event(key: Qt.Key, text: str = '') -> QKeyEvent:
        return QKeyEvent(
            QKeyEvent.Type.KeyPress,
            key,
            Qt.KeyboardModifier.NoModifier,
            text,
        )

    chars = []
    app = type('KeyApp', (), {})()
    app._key_chars = {}
    app.focus_in_control_panel = False
    app.tuney = type('Tuney', (), {})()
    app.tuney.state = type('TuneyState', (), {'on_char': chars.append})()
    app._on_key_event = lambda event, is_press: MainWindow._on_key_event(
        app, event, is_press
    )
    main_window_module.time.time = lambda: 100.0

    assert MainWindow.eventFilter(app, app, key_event(Qt.Key.Key_A, 'a'))
    assert chars == [CharPress('a', time=100.0)]

    chars.clear()
    app.focus_in_control_panel = True
    assert not MainWindow.eventFilter(app, app, key_event(Qt.Key.Key_A, 'a'))
    assert chars == []


def test_app_mainloop_exits_on_sigint() -> None:
    calls = []
    handlers = []

    class Signal:
        def __init__(self) -> None:
            self.callback = None

        def connect(self, callback: object) -> None:
            self.callback = callback

    class FakeTimer:
        def __init__(self, parent: object) -> None:
            calls.append(('timer', parent))
            self.timeout = Signal()

        def start(self, delay: int) -> None:
            calls.append(('start', delay))

        def stop(self) -> None:
            calls.append('stop')

        def deleteLater(self) -> None:
            calls.append('delete')

    class FakeQtApp:
        def exec(self) -> None:
            handlers[-1][1](signal.SIGINT, None)
            calls.append('exec')

        def quit(self) -> None:
            calls.append('quit')

    main_window_module.QTimer = FakeTimer
    main_window_module.signal.getsignal = lambda signum: 'old'
    main_window_module.signal.signal = lambda signum, handler: handlers.append(
        (signum, handler)
    )

    app = type(
        'LoopApp',
        (),
        {
            'qt_app': FakeQtApp(),
            'activate': lambda self: calls.append('activate'),
            'close': lambda self: calls.append('close'),
            '_on_sigint': lambda self, signum, frame: MainWindow._on_sigint(
                self, signum, frame
            ),
        },
    )()

    MainWindow.mainloop(app)

    assert calls == [
        ('timer', app),
        ('start', SIGNAL_POLL_IN_MS),
        'activate',
        'close',
        'quit',
        'exec',
        'stop',
        'delete',
    ]
    assert handlers[0][0] == signal.SIGINT
    assert callable(handlers[0][1])
    assert handlers[-1] == (signal.SIGINT, 'old')


def test_application_uses_cross_platform_style() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'state.toml'
        window = MainWindow(Tuney(gui=True, silent=True, autosave_file=path))
        app = window.qt_app

        assert app.applicationName() == 'Tuney'
        assert app.style().objectName().lower() == 'fusion'
        window.close()


def test_app_activate_and_history() -> None:
    calls = []
    app = type(
        'ActivateApp',
        (),
        {
            'show': lambda self: calls.append('show'),
            'raise_': lambda self: calls.append('raise'),
            'activateWindow': lambda self: calls.append('activate'),
            'setFocus': lambda self: calls.append('focus'),
            '_has_focus': False,
        },
    )()

    MainWindow.activate(app)
    assert calls == ['show', 'raise', 'activate', 'focus']
    assert app._has_focus

    app = HistoryApp()
    app.history.checkpoint_undo()
    object.__setattr__(app.tuney, 'max_gap', 2.0)
    app.history.loop_before = 0.5
    app.history.undo()

    assert app.tuney.max_gap == 1.0
    assert app.history.loop_before == 0.0

    app.history.redo()

    assert app.tuney.max_gap == 2.0
    assert app.history.loop_before == 0.5

    object.__setattr__(app.tuney, 'max_gap', 3.0)
    object.__setattr__(app.tuney, 'text', [CharPress('a', time=0.0)])
    app.tuney.state.__dict__.pop('char_presses', None)
    app.history.loop_replay = True
    app.history.loop_before = 0.25
    app.history.loop_after = 0.5
    app.history.loop_tempo = 2.0
    app.history.randomize_on_each_loop = True

    app.history.clear_settings()

    assert app.tuney.max_gap == Tuney().max_gap
    assert app.tuney.state.char_presses == []
    assert app.tuney.gui
    assert not app.history.loop_replay
    assert app.history.loop_before == 0.0
    assert app.history.loop_after == 0.0
    assert app.history.loop_tempo == 1.0
    assert not app.history.randomize_on_each_loop

    with tempfile.TemporaryDirectory() as tmp:
        os.environ['XDG_STATE_HOME'] = tmp
        messages = []

        class FakeMessageBox:
            @staticmethod
            def information(parent: object, title: str, text: str) -> None:
                messages.append((parent, title, text))

        main_window_module.QMessageBox = FakeMessageBox
        MainWindow.on_show_log(app)

        assert messages == [
            (
                app,
                'Tuney log',
                f'Log file:\n\n{Path(tmp) / "tuney" / "tuney.txt"}',
            )
        ]


class FakeLoop:
    def select(self) -> None:
        pass

    def deselect(self) -> None:
        pass


class FakeLayout:
    loop = FakeLoop()
    randomize_on_each_loop = FakeLoop()

    def set_text(self, text: object) -> None:
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


class HistoryApp:
    def __init__(self) -> None:
        self.tuney = Tuney(max_gap=1.0)
        self.ui = FakeLayout()
        self.history = History(self)
