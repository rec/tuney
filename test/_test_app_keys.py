import os
import signal
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeyEvent

from tuney.app.app import App
from tuney.scale.ratios import Ratios
from tuney.scale.tuning import Computed, Type
from tuney.time.char_press import CharPress
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
    app.app = object()
    main_window_module.on_char = lambda _, c: chars.append(c)
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
    app.app = object()
    main_window_module.on_char = lambda _, c: chars.append(c)
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
        window = MainWindow(App(gui=True, silent=True, autosave_file=path))
        app = window.qt_app

        assert app.applicationName() == 'Tuney'
        assert app.style().objectName().lower() == 'fusion'
        menu_actions: dict[str, list[str]] = {}
        for action in window.menuBar().actions():
            if (menu := action.menu()) is not None:
                menu_actions[action.text()] = [i.text() for i in menu.actions()]
        edit_actions = menu_actions['Edit']
        file_actions = menu_actions['File']

        assert 'Clear' in edit_actions
        assert 'Clear Text' in edit_actions
        assert 'Clear' not in file_actions
        assert 'Clear Text' not in file_actions
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
    object.__setattr__(app.app, 'max_gap', 2.0)
    app.history.loop_before = 0.5
    app.history.undo()

    assert app.app.max_gap == 1.0
    assert app.history.loop_before == 0.0

    app.history.redo()

    assert app.app.max_gap == 2.0
    assert app.history.loop_before == 0.5

    object.__setattr__(app.app, 'max_gap', 3.0)
    object.__setattr__(app.app, 'text', [CharPress('a', time=0.0)])
    app.app.__dict__.pop('char_presses', None)
    app.history.loop_replay = True
    app.history.loop_before = 0.25
    app.history.loop_after = 0.5
    app.history.loop_tempo = 2.0
    app.history.randomize_on_each_loop = True

    app.history.clear_settings()

    assert app.app.max_gap == App().max_gap
    assert app.app.char_presses == []
    assert not app.app.gui
    assert not app.history.loop_replay
    assert app.history.loop_before == 0.0
    assert app.history.loop_after == 0.0
    assert app.history.loop_tempo == 1.0
    assert not app.history.randomize_on_each_loop
    app.history.undo()

    assert app.app.max_gap == 3.0
    assert app.app.display_text == 'a'

    app = HistoryApp()
    app.app.__dict__['main_window'] = app
    object.__setattr__(app.app, 'gui', True)
    object.__setattr__(app.app, 'max_gap', 3.0)
    object.__setattr__(app.app, 'text', [CharPress('a', time=0.0)])
    app.app.__dict__.pop('char_presses', None)

    MainWindow.on_clear(app)

    data = App().model_dump()
    data['gui'] = True
    assert app.app.model_dump() == data
    assert app.app.char_presses == []
    assert app.ui.text == ''
    app.history.undo()

    assert app.app.max_gap == 3.0
    assert app.app.display_text == 'a'

    object.__setattr__(app.app, 'max_gap', 4.0)
    MainWindow.on_clear_text(app)

    assert app.app.max_gap == 4.0
    assert app.app.char_presses == []
    assert app.ui.text == ''
    app.history.undo()

    assert app.app.max_gap == 4.0
    assert app.app.display_text == 'a'

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

    opened = []

    class FakeDesktopServices:
        @staticmethod
        def openUrl(url: QUrl) -> bool:
            opened.append(url.toLocalFile())
            return True

    main_window_module.QDesktopServices = FakeDesktopServices

    with tempfile.TemporaryDirectory() as tmp:
        config_file = Path(tmp) / 'configs' / 'settings.toml'
        object.__setattr__(app.app, 'config_file', config_file)
        MainWindow.on_open_config_folder(app)

        assert [Path(i).resolve() for i in opened] == [config_file.parent.resolve()]
        assert config_file.parent.is_dir()

    with tempfile.TemporaryDirectory() as tmp:
        opened.clear()
        autosave_file = Path(tmp) / 'state' / 'state.toml'
        app = HistoryApp()
        object.__setattr__(app.app, 'autosave_file', autosave_file)
        MainWindow.on_open_config_folder(app)

        assert [Path(i).resolve() for i in opened] == [autosave_file.parent.resolve()]
        assert autosave_file.parent.is_dir()


def test_app_imports_and_exports_tuning() -> None:
    app = HistoryApp()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'input.scl'
        Ratios(ratios=[2], name='input.scl', desc='one step').write_scala_file(path)

        class FakeOpenDialog:
            @staticmethod
            def getOpenFileName(*_: object) -> tuple[str, str]:
                return str(path), ''

        main_window_module.QFileDialog = FakeOpenDialog

        MainWindow.on_import_tuning(app)

    assert app.history.undo_stack
    assert app.app.tuning.ratios == Ratios(
        ratios=[2], name='input.scl', desc='one step'
    )
    assert app.ui.rebuild_control_panel_count == 1

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'output.scl'

        class FakeSaveDialog:
            @staticmethod
            def getSaveFileName(*_: object) -> tuple[str, str]:
                return str(path), ''

        main_window_module.QFileDialog = FakeSaveDialog

        MainWindow.on_export_tuning(app)

        assert Ratios.read_scala_file(path).ratios == [2]

    app = HistoryApp()
    object.__setattr__(
        app.app,
        'tuning',
        app.app.tuning.model_copy(
            update={'type': Type.computed, 'computed': Computed(octave_ratio=4)}
        ),
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'computed.scl'

        class FakeComputedSaveDialog:
            @staticmethod
            def getSaveFileName(*_: object) -> tuple[str, str]:
                return str(path), ''

        main_window_module.QFileDialog = FakeComputedSaveDialog

        MainWindow.on_export_tuning(app)

        assert (
            Ratios.read_scala_file(path).ratios
            == Computed(octave_ratio=4).as_ratios().ratios
        )

    class FakeAction:
        def __init__(self) -> None:
            self.enabled = True

        def setEnabled(self, enabled: bool) -> None:
            self.enabled = enabled

    app.export_tuning_action = FakeAction()
    MainWindow._update_export_tuning_action(app)
    assert app.export_tuning_action.enabled

    object.__setattr__(
        app.app,
        'tuning',
        app.app.tuning.model_copy(update={'type': Type.table, 'table': [440]}),
    )
    MainWindow._update_export_tuning_action(app)
    assert not app.export_tuning_action.enabled


class FakeLoop:
    def select(self) -> None:
        pass

    def deselect(self) -> None:
        pass


class FakeLayout:
    def __init__(self) -> None:
        self.loop = FakeLoop()
        self.randomize_on_each_loop = FakeLoop()
        self.rebuild_control_panel_count = 0
        self.text = None

    def set_text(self, text: object) -> None:
        self.text = text

    def rebuild_control_panel(self) -> None:
        self.rebuild_control_panel_count += 1

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
        self.app = App(max_gap=1.0)
        self.ui = FakeLayout()
        self.history = History(self)

    _set_tuning = MainWindow._set_tuning
