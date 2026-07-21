import os
import signal
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeyEvent, QKeySequence

from tuney import presets as presets_module
from tuney.app.app import App
from tuney.app.global_config import GlobalConfig
from tuney.mapper.mapper import Mapper
from tuney.scale.ratios import Ratios
from tuney.scale.table import Table
from tuney.scale.tuning import Computed, Tuning, Type
from tuney.time.char_press import CharPress
from tuney.ui import file_dialogs as file_dialogs_module
from tuney.ui import main_window as main_window_module
from tuney.ui import startup
from tuney.ui.history import History
from tuney.ui.main_window import SIGNAL_POLL_IN_MS, MainWindow


def run(names: list[str]) -> None:
    for name in names:
        globals()[name]()


def _shortcut_text(shortcuts: list[QKeySequence]) -> str:
    return ', '.join(
        i.toString(QKeySequence.SequenceFormat.PortableText) for i in shortcuts
    )


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


def test_macos_option_composed_characters() -> None:
    chars = []
    app = type('KeyApp', (), {})()
    app._key_chars = {}
    app.app = object()
    main_window_module.on_char = lambda _, c: chars.append(c)
    main_window_module.time.time = iter([100.0, 100.25]).__next__
    platform = main_window_module.sys.platform
    main_window_module.sys.platform = 'darwin'

    try:
        assert MainWindow._on_key_event(
            app,
            QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_E,
                Qt.KeyboardModifier.AltModifier,
                'é',
            ),
            True,
        )
        assert MainWindow._on_key_event(
            app,
            QKeyEvent(
                QKeyEvent.Type.KeyRelease,
                Qt.Key.Key_E,
                Qt.KeyboardModifier.NoModifier,
            ),
            False,
        )
    finally:
        main_window_module.sys.platform = platform

    assert chars == [
        CharPress('é', time=100.0),
        CharPress('é', False, time=100.25),
    ]


def test_macos_option_special_keys_remain_ignored() -> None:
    chars = []
    app = type('KeyApp', (), {})()
    app._key_chars = {}
    app.app = object()
    main_window_module.on_char = lambda _, c: chars.append(c)
    platform = main_window_module.sys.platform
    main_window_module.sys.platform = 'darwin'

    try:
        assert not MainWindow._on_key_event(
            app,
            QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_Backspace,
                Qt.KeyboardModifier.AltModifier,
                '',
            ),
            True,
        )
    finally:
        main_window_module.sys.platform = platform

    assert chars == []


def test_non_macos_alt_characters_remain_ignored() -> None:
    chars = []
    app = type('KeyApp', (), {})()
    app._key_chars = {}
    app.app = object()
    main_window_module.on_char = lambda _, c: chars.append(c)
    platform = main_window_module.sys.platform
    main_window_module.sys.platform = 'linux'

    try:
        assert not MainWindow._on_key_event(
            app,
            QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_E,
                Qt.KeyboardModifier.AltModifier,
                'é',
            ),
            True,
        )
    finally:
        main_window_module.sys.platform = platform

    assert chars == []


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

    old_timer = main_window_module.QTimer
    old_getsignal = main_window_module.signal.getsignal
    old_signal = main_window_module.signal.signal

    try:
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
    finally:
        main_window_module.QTimer = old_timer
        main_window_module.signal.getsignal = old_getsignal
        main_window_module.signal.signal = old_signal

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
    from PySide6.QtWidgets import QWidget

    from tuney.ui import layout as layout_module

    class FakeControlPanel:
        show_advanced = True

        def show_mode(self, checked: bool) -> None:
            self.show_advanced = checked

    class FakeTextItem:
        def __init__(self, text: str) -> None:
            self._text = text

        def text(self) -> str:
            return self._text

    class FakeTextTimings:
        def __init__(self) -> None:
            self.rows: list[list[str]] = []

        def rowCount(self) -> int:
            return len(self.rows)

        def item(self, row: int, column: int) -> FakeTextItem:
            return FakeTextItem(self.rows[row][column])

    class FakeWindowLayout(QWidget):
        def __init__(self, window: MainWindow) -> None:
            super().__init__(window)
            self.control_panel = FakeControlPanel()
            self.text_timings = FakeTextTimings()

        def set_text(self, _text: str) -> None:
            pass

        def set_text_timings(self, rows: list[list[str]]) -> None:
            self.text_timings.rows = rows

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'state.toml'
        startup.autosave_file = path
        old_layout = layout_module.Layout
        try:
            layout_module.Layout = FakeWindowLayout
            window = MainWindow(App(gui=True, silent=True))
        finally:
            layout_module.Layout = old_layout
        app = window.qt_app

        assert app.applicationName() == 'Tuney'
        assert app.style().objectName().lower() == 'fusion'
        menu_actions: dict[str, list[str]] = {}
        action_shortcuts: dict[str, str] = {}
        for action in window.menuBar().actions():
            if (menu := action.menu()) is not None:
                menu_actions[action.text()] = [i.text() for i in menu.actions()]
                action_shortcuts |= {
                    i.text(): _shortcut_text(i.shortcuts()) for i in menu.actions()
                }
        edit_actions = menu_actions['Edit']
        file_actions = menu_actions['File']

        assert all(action_shortcuts.values())
        help_shortcut = action_shortcuts.pop('Tuney Help')
        assert help_shortcut in {'Ctrl+?, Help', 'F1, Help'}
        expected_shortcuts = {
            'Undo': 'Ctrl+Z',
            'Redo': 'Ctrl+Y',
            'Randomize Timing': 'Ctrl+R',
            'Randomize Settings': 'Ctrl+Alt+R',
            'Clear': 'Ctrl+B',
            'Clear Text': 'Ctrl+Alt+B',
            'Show Text Timings': 'Ctrl+T',
            'Advanced': 'Ctrl+Alt+A',
            'Open Text File': 'Ctrl+O',
            'Save preset...': 'Ctrl+P',
            'Delete presets...': 'Ctrl+Alt+P',
            'Import tuning...': 'Ctrl+I',
            'Export tuning...': 'Ctrl+E',
            'Save': 'Ctrl+S',
            'Save as Audio...': 'Ctrl+Alt+E',
            'Open enclosing folder for config file': 'Ctrl+Alt+O',
            'Put Config file in Trash': 'Ctrl+Alt+Del',
            'Copy from state': 'Ctrl+Alt+C',
            'Paste into state': 'Ctrl+Alt+V',
            'Load autosave on start': 'Ctrl+L',
            'Swap with autosave': 'Ctrl+Alt+S',
            'Refresh Devices': 'Ctrl+D',
            'Show Log Location': 'Ctrl+Alt+L',
            'Report a problem...': 'Ctrl+Alt+I',
        }
        assert action_shortcuts == expected_shortcuts, action_shortcuts
        assert 'Save preset...' in file_actions
        assert 'Save as Audio...' in file_actions
        assert 'Delete presets...' in file_actions
        assert 'Load autosave on start' in file_actions
        assert 'Swap with autosave' in file_actions
        assert 'Advanced' in edit_actions
        assert 'Show Text Timings' in edit_actions
        assert 'Randomize Settings' in edit_actions
        assert 'Clear' in edit_actions
        assert 'Clear Text' in edit_actions
        assert 'Clear' not in file_actions
        assert 'Clear Text' not in file_actions
        assert window.show_text_timings_action.isCheckable()
        assert not window.show_text_timings_action.isChecked()
        assert window.advanced_action.isCheckable()
        assert window.advanced_action.isChecked()

        window.app.text = [CharPress('a', time=0.0), CharPress('a', False, 25.0)]
        window.app.__dict__.pop('char_presses', None)
        window.show_text_timings_action.trigger()

        assert window.app.show_text_timings
        assert window.ui.text_timings.rowCount() == 1
        assert window.ui.text_timings.item(0, 0).text() == 'a'
        assert window.ui.text_timings.item(0, 1).text() == '0'
        assert window.ui.text_timings.item(0, 2).text() == '25'

        window.advanced_action.trigger()

        assert not window.ui.control_panel.show_advanced
        window.close()


def test_loop_state_restoration_does_not_retoggle_checkboxes() -> None:
    app = HistoryApp()

    app.history.loop_replay = False

    assert app.ui.loop.calls == []

    app.history.loop_replay = True

    assert app.ui.loop.calls == ['select']

    app.ui.loop.calls.clear()
    app.history.loop_replay = True

    assert app.ui.loop.calls == []


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
    app.app.max_gap = 2.0
    app.history.loop_before = 0.5
    app.history.undo()

    assert app.app.max_gap == 1.0
    assert app.history.loop_before == 0.0

    app.history.redo()

    assert app.app.max_gap == 2.0
    assert app.history.loop_before == 0.5

    app.app.max_gap = 3.0
    app.app.mapper = Mapper(alphabet='abc')
    app.app.text = [CharPress('a', time=0.0)]
    app.app.__dict__.pop('char_presses', None)
    app.history.loop_replay = True
    app.history.loop_before = 0.25
    app.history.loop_after = 0.5
    app.history.loop_tempo = 2.0
    app.history.randomize_on_each_loop = True

    app.history.clear_settings()

    assert app.app.max_gap == App().max_gap
    assert app.app.mapper.alphabet is None
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
    app.app.gui = True
    app.app.max_gap = 3.0
    app.app.text = [CharPress('a', time=0.0)]
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

    app.app.max_gap = 4.0
    MainWindow.on_clear_text(app)

    assert app.app.max_gap == 4.0
    assert app.app.char_presses == []
    assert app.ui.text == ''
    app.history.undo()

    assert app.app.max_gap == 4.0
    assert app.app.display_text == 'a'

    app.app.load_autosave = True
    MainWindow.on_load_autosave(app, False)

    assert not app.app.load_autosave
    app.history.undo()

    assert app.app.load_autosave

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'state.toml'
        startup.autosave_file = path
        app.app.__dict__.pop('_autosave', None)
        autosaved = App(gui=False, max_gap=2.0, load_autosave=False)
        autosaved._autosave.save(lambda path: main_window_module.save(autosaved, path))
        app.app.max_gap = 3.0
        app.app.load_autosave = True

        MainWindow.on_swap_with_autosave(app)

        assert app.app.max_gap == 2.0
        assert not app.app.load_autosave
        assert App.model_validate(presets_module.read_file(path)).max_gap == 3.0
        app.history.undo()

        assert app.app.max_gap == 3.0
        assert app.app.load_autosave

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
        app.app.config_file = config_file
        MainWindow.on_open_config_folder(app)

        assert [Path(i).resolve() for i in opened] == [config_file.parent.resolve()]
        assert config_file.parent.is_dir()

    with tempfile.TemporaryDirectory() as tmp:
        opened.clear()
        autosave_file = Path(tmp) / 'state' / 'state.toml'
        app = HistoryApp()
        startup.autosave_file = autosave_file
        MainWindow.on_open_config_folder(app)

        assert [Path(i).resolve() for i in opened] == [autosave_file.parent.resolve()]
        assert autosave_file.parent.is_dir()

    trashed = []

    class FakeFile:
        @staticmethod
        def moveToTrash(path: str) -> bool:
            trashed.append(path)
            return True

    main_window_module.QFile = FakeFile

    with tempfile.TemporaryDirectory() as tmp:
        config_file = Path(tmp) / 'configs' / 'settings.toml'
        config_file.parent.mkdir()
        config_file.write_text('max_gap = 2.0\n')
        app = HistoryApp()
        app.app.config_file = config_file
        MainWindow.on_trash_config_file(app)

        assert [Path(i).resolve() for i in trashed] == [config_file.resolve()]

    with tempfile.TemporaryDirectory() as tmp:
        trashed.clear()
        autosave_file = Path(tmp) / 'state' / 'state.toml'
        autosave_file.parent.mkdir()
        autosave_file.write_text('max_gap = 2.0\n')
        app = HistoryApp()
        startup.autosave_file = autosave_file
        MainWindow.on_trash_config_file(app)

        assert [Path(i).resolve() for i in trashed] == [autosave_file.resolve()]


def test_app_reports_problem() -> None:
    opened: list[str] = []

    class FakeDesktopServices:
        @staticmethod
        def openUrl(url: QUrl) -> bool:
            opened.append(url.toString())
            return True

    main_window_module.QDesktopServices = FakeDesktopServices
    app = HistoryApp()

    MainWindow.on_report_problem(app)

    assert opened
    assert opened[0].startswith('https://github.com/rec/tuney/issues/new?')
    assert 'Tuney+problem+report' in opened[0]


def test_app_imports_and_exports_tuning() -> None:
    app = HistoryApp()

    with tempfile.TemporaryDirectory() as tmp:
        app.app.__dict__['global_config'] = GlobalConfig(file=Path(tmp) / 'global.toml')
        path = Path(tmp) / 'input.scl'
        Ratios(text='2', name='input.scl', desc='one step').write_scala_file(path)

        class FakeOpenDialog:
            @staticmethod
            def getOpenFileName(*_: object) -> tuple[str, str]:
                return str(path), ''

        file_dialogs_module.QFileDialog = FakeOpenDialog

        MainWindow.on_import_tuning(app)

    assert app.history.undo_stack
    assert app.app.tuning.ratios == Ratios(text='2', name='input.scl', desc='one step')
    assert app.ui.rebuild_control_panel_count == 1

    with tempfile.TemporaryDirectory() as tmp:
        app.app.__dict__['global_config'] = GlobalConfig(file=Path(tmp) / 'global.toml')
        path = Path(tmp) / 'output.scl'

        class FakeSaveDialog:
            @staticmethod
            def getSaveFileName(*_: object) -> tuple[str, str]:
                return str(path), ''

        file_dialogs_module.QFileDialog = FakeSaveDialog

        MainWindow.on_export_tuning(app)

        assert Ratios.read_scala_file(path).ratios == [2]

    app = HistoryApp()
    app.app.tuning = app.app.tuning.model_copy(
        update={'type': Type.computed, 'computed': Computed(octave_ratio=4)}
    )

    with tempfile.TemporaryDirectory() as tmp:
        app.app.__dict__['global_config'] = GlobalConfig(file=Path(tmp) / 'global.toml')
        path = Path(tmp) / 'computed.scl'

        class FakeComputedSaveDialog:
            @staticmethod
            def getSaveFileName(*_: object) -> tuple[str, str]:
                return str(path), ''

        file_dialogs_module.QFileDialog = FakeComputedSaveDialog

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

    app.app.tuning = app.app.tuning.model_copy(
        update={'type': Type.table, 'table': Table(text='440')}
    )
    MainWindow._update_export_tuning_action(app)
    assert not app.export_tuning_action.enabled

    app.app.tuning = Tuning(type=Type.table, table=None, computed=None, ratios=None)
    MainWindow._update_export_tuning_action(app)
    assert not app.export_tuning_action.enabled


def test_file_dialogs_remember_last_directories() -> None:
    app = HistoryApp()

    with tempfile.TemporaryDirectory() as tmp:
        first = Path(tmp) / 'first' / 'input.txt'
        second = Path(tmp) / 'second' / 'output.toml'
        calls: list[str] = []
        app.app.__dict__['global_config'] = GlobalConfig(file=Path(tmp) / 'global.toml')

        class FakeDialog:
            @staticmethod
            def getOpenFileName(*args: object) -> tuple[str, str]:
                calls.append(str(args[2]))
                return str(first), ''

            @staticmethod
            def getSaveFileName(*args: object) -> tuple[str, str]:
                calls.append(str(args[2]))
                return str(second), ''

        file_dialogs_module.QFileDialog = FakeDialog

        MainWindow._get_open_file_name(app, 'Open Text File', 'Open Text File', '*')
        MainWindow._get_save_file_name(app, 'Save', 'Save', '*')
        MainWindow._get_open_file_name(app, 'Open Text File', 'Open Text File', '*')
        MainWindow._get_save_file_name(app, 'Save', 'Save', '*')

    assert calls == ['', '', str(first.parent), str(second.parent)]


def test_app_saves_audio_from_current_text() -> None:
    app = HistoryApp()
    app.app.text = [
        CharPress('a', time=0),
        CharPress('a', False, 100),
    ]
    app.app.__dict__.pop('char_presses', None)
    rendered = []

    with tempfile.TemporaryDirectory() as tmp:
        app.app.__dict__['global_config'] = GlobalConfig(file=Path(tmp) / 'global.toml')
        path = Path(tmp) / 'out.wav'

        class FakeSaveDialog:
            @staticmethod
            def getSaveFileName(*_: object) -> tuple[str, str]:
                return str(path), ''

        def render_file(output, events, comment):
            rendered.append((output, events, comment))

        file_dialogs_module.QFileDialog = FakeSaveDialog
        app.app.__dict__['player'] = type(
            'FakePlayer',
            (),
            {'render_file': staticmethod(render_file), 'sample_rate': 48_000},
        )()

        MainWindow.on_save_as_audio(app)

    output, events, comment = rendered[0]
    assert output == path
    assert [(frame, note.is_press) for frame, note in events] == [
        (0, True),
        (4800, False),
    ]
    assert callable(comment)


def test_app_saves_and_deletes_presets() -> None:
    app = HistoryApp()
    old_user_presets = presets_module.USER_PRESETS
    old_input_dialog = main_window_module.QInputDialog
    old_selected_preset_names = main_window_module._selected_preset_names
    try:
        with tempfile.TemporaryDirectory() as tmp:
            presets_module.USER_PRESETS = Path(tmp)

            class FakeInputDialog:
                @staticmethod
                def getText(*_: object) -> tuple[str, bool]:
                    return 'mine', True

            main_window_module.QInputDialog = FakeInputDialog
            app.app.max_gap = 2.0

            MainWindow.on_save_preset(app)

            path = Path(tmp) / 'mine.toml'
            assert path.exists()
            assert presets_module.read_preset('mine')['max_gap'] == 2.0

            main_window_module._selected_preset_names = lambda _: ['mine']

            MainWindow.on_delete_presets(app)

            assert not path.exists()

            app.history.undo()

            assert path.exists()

            app.history.redo()

            assert not path.exists()
    finally:
        presets_module.USER_PRESETS = old_user_presets
        main_window_module.QInputDialog = old_input_dialog
        main_window_module._selected_preset_names = old_selected_preset_names


class FakeLoop:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def select(self) -> None:
        self.calls.append('select')

    def deselect(self) -> None:
        self.calls.append('deselect')


class FakeAction:
    def __init__(self) -> None:
        self.checked = False

    def setChecked(self, checked: bool) -> None:
        self.checked = checked


class FakeLayout:
    def __init__(self) -> None:
        self.loop = FakeLoop()
        self.randomize_on_each_loop = FakeLoop()
        self.rebuild_control_panel_count = 0
        self.text = None
        self.text_timings = None

    def set_text(self, text: object) -> None:
        self.text = text

    def set_text_timings(self, rows: list[list[str]]) -> None:
        self.text_timings = rows

    def set_active_text_timing(self, index: int | None) -> None:
        pass

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
        self.load_autosave_action = FakeAction()
        self.show_text_timings_action = FakeAction()

    def update_text_display(self) -> None:
        if self.app.show_text_timings:
            self.ui.set_text_timings(self.app.display_text_timings)
        else:
            self.ui.set_text(self.app.display_text)

    def sync_config_actions(self) -> None:
        self.load_autosave_action.setChecked(self.app.load_autosave)
        self.show_text_timings_action.setChecked(self.app.show_text_timings)

    _set_tuning = MainWindow._set_tuning
    _get_open_file_name = MainWindow._get_open_file_name
    _get_save_file_name = MainWindow._get_save_file_name
    _config_path = MainWindow._config_path
