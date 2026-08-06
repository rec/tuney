from pytest import MonkeyPatch

import tuney.ui.layout
import tuney.ui.main_menu
import tuney.ui.main_window
import tuney.ui.theme
from tuney.app.global_config import GlobalConfig
from tuney.ui.control_panel_layout import _FlowLayout
from tuney.ui.layout import Layout


def test_normal_play_cursor_shows_at_text_end() -> None:
    layout = Layout.__new__(Layout)
    textbox = _FakeTextBox('abc')
    layout.textbox = textbox
    layout.text_stack = _FakeTextStack(textbox)

    layout.set_play_cursor(None)

    assert textbox.clear_focus_count == 0
    assert textbox.cursor.position == 3
    assert textbox.focus_count == 1


def test_normal_play_cursor_ignores_hidden_textbox() -> None:
    layout = Layout.__new__(Layout)
    textbox = _FakeTextBox('abc')
    layout.textbox = textbox
    layout.text_stack = _FakeTextStack(object())

    layout.set_play_cursor(None)

    assert textbox.cursor.position is None
    assert textbox.focus_count == 0


def test_note_grid_reuses_buttons() -> None:
    from PySide6.QtWidgets import QApplication, QGridLayout, QWidget

    if QApplication.instance() is None:
        QApplication([])

    layout = Layout.__new__(Layout)
    layout.main_window = _FakeMainWindow()
    layout.note_grid_widget = QWidget()
    layout.note_grid = QGridLayout(layout.note_grid_widget)
    layout.splitter = _FakeSplitter()
    layout.__dict__['note_button_cache'] = {}

    layout.rebuild_note_grid()
    first_a = layout.note_buttons['a']
    first_b = layout.note_buttons['b']

    layout.main_window.app.labels = {'a': 'A2'}
    layout.rebuild_note_grid()

    assert layout.note_buttons == {'a': first_a}
    assert layout.note_buttons['a'].note_name == 'A2'
    assert layout.note_buttons['a'].tooltip.text == 'A2\n440 Hz'
    assert first_b.isHidden()
    assert first_b.parent() is layout.note_grid_widget


def test_note_grid_tooltips_include_note_frequency() -> None:
    from PySide6.QtWidgets import QApplication, QGridLayout, QWidget

    if QApplication.instance() is None:
        QApplication([])

    layout = Layout.__new__(Layout)
    layout.main_window = _FakeMainWindow()
    layout.note_grid_widget = QWidget()
    layout.note_grid = QGridLayout(layout.note_grid_widget)
    layout.splitter = _FakeSplitter()
    layout.__dict__['note_button_cache'] = {}

    layout.rebuild_note_grid()

    assert layout.note_buttons['a'].tooltip.text == 'A\n440 Hz'
    assert layout.note_buttons['b'].tooltip.text == 'B\n466.164 Hz'


def test_note_grid_updates_program_minimum_height() -> None:
    from PySide6.QtWidgets import QApplication, QGridLayout, QWidget

    if QApplication.instance() is None:
        QApplication([])

    layout = Layout.__new__(Layout)
    layout.main_window = _FakeMainWindow()
    layout.note_grid_widget = QWidget()
    layout.note_grid = QGridLayout(layout.note_grid_widget)
    layout.splitter = _FakeSplitter()
    layout.__dict__['note_button_cache'] = {}

    layout.rebuild_note_grid()

    assert layout.note_grid_widget.minimumHeight() == tuney.ui.layout.MIN_BUTTON_HEIGHT
    assert layout.main_window.minimum_content_height == (
        tuney.ui.layout._minimum_program_height(1, _FakeSplitter.handle_width)
    )
    assert layout.main_window.enforce_minimum_size_count == 1


def test_program_minimum_size_resizes_without_qt_minimum_constraints() -> None:
    assert tuney.ui.main_window.MIN_PROGRAM_WIDTH == 500

    window = _FakeResizeWindow(width=320, height=120, minimum_content_height=360)

    tuney.ui.main_window.MainWindow.enforce_minimum_size(window)

    assert window.sizes == [(500, 360)]


def test_theme_lookup_returns_light_and_dark_palettes() -> None:
    assert (
        tuney.ui.theme.theme_for_name(tuney.ui.theme.ThemeName.light)
        is tuney.ui.theme.LIGHT_THEME
    )
    assert tuney.ui.theme.theme_for_name('dark') is tuney.ui.theme.DARK_THEME
    assert tuney.ui.theme.theme_for_name('unknown') is tuney.ui.theme.LIGHT_THEME


def test_app_theme_sets_palette_roles() -> None:
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    if (app := QApplication.instance()) is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    palette = app.palette()
    for role in (
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.Window,
    ):
        palette.setColor(role, QColor('#000000'))
    app.setPalette(palette)

    tuney.ui.theme.set_app_theme(app, tuney.ui.theme.DARK_THEME)

    for role in (
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.Window,
    ):
        assert app.palette().color(role).name() in {
            tuney.ui.theme.DARK_THEME.alternate_base,
            tuney.ui.theme.DARK_THEME.base,
            tuney.ui.theme.DARK_THEME.button,
            tuney.ui.theme.DARK_THEME.window,
        }
    for role in (
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
    ):
        assert app.palette().color(role).name() == tuney.ui.theme.DARK_THEME.text


def test_dark_mode_menu_action_reflects_global_config_theme() -> None:
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        QApplication([])
    window = _FakeMenuWindow(tuney.ui.theme.ThemeName.dark)

    tuney.ui.main_menu.build_menu(window)

    assert window.dark_mode_action.isChecked()


def test_dark_mode_toggle_saves_theme_and_refreshes_widgets(tmp_path) -> None:
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    if (qt_app := QApplication.instance()) is None:
        qt_app = QApplication([])
    assert isinstance(qt_app, QApplication)
    config = GlobalConfig(file=tmp_path / 'global.toml')
    window = _FakeThemeWindow(config, qt_app)

    tuney.ui.main_window.MainWindow.on_dark_mode(window, True)

    assert GlobalConfig.read(config.path).theme == tuney.ui.theme.ThemeName.dark
    assert window.refresh_count == 1
    assert (
        qt_app.palette().color(QPalette.ColorRole.Window).name()
        == tuney.ui.theme.DARK_THEME.window
    )


def test_program_minimum_size_enforcement_waits_for_mouse_release(
    monkeypatch: MonkeyPatch,
) -> None:
    window = _FakeResizeWindow(width=320, height=120, minimum_content_height=360)
    timer = _FakeMinimumSizeTimer()
    window._minimum_size_timer = timer
    monkeypatch.setattr(
        tuney.ui.main_window.QtWidgets, 'QApplication', _FakePressedApplication
    )

    tuney.ui.main_window.MainWindow._enforce_minimum_size_after_resize(window)

    assert timer.delays == [tuney.ui.main_window.MINIMUM_SIZE_ENFORCEMENT_DELAY_IN_MS]
    assert window.sizes == []

    monkeypatch.setattr(
        tuney.ui.main_window.QtWidgets, 'QApplication', _FakeReleasedApplication
    )

    tuney.ui.main_window.MainWindow._enforce_minimum_size_after_resize(window)

    assert timer.delays == [tuney.ui.main_window.MINIMUM_SIZE_ENFORCEMENT_DELAY_IN_MS]
    assert window.sizes == [(500, 360)]


def test_master_gain_has_numeric_box_synced_with_dial() -> None:
    from PySide6.QtWidgets import (
        QApplication,
        QDial,
        QDoubleSpinBox,
        QVBoxLayout,
        QWidget,
    )

    if QApplication.instance() is None:
        QApplication([])

    layout = Layout.__new__(Layout)
    layout.main_window = _FakeMainWindow()
    layout.text_area = QWidget()
    layout.text_area_layout = QVBoxLayout(layout.text_area)

    frame = Layout.replay_frame.func(layout)
    spin = frame.findChild(QDoubleSpinBox, 'master_gain')
    dial = frame.findChild(QDial, 'master_gain_dial')

    assert spin is not None
    assert dial is not None
    assert spin.decimals() == 4
    assert spin.singleStep() == 0.01
    assert spin.value() == 1.2345
    assert dial.value() == 123

    spin.setValue(0.5)

    assert dial.value() == 50
    assert layout.main_window.master_gains[-1] == 0.5

    dial.setValue(75)

    assert spin.value() == 0.75
    assert layout.main_window.master_gains[-1] == 0.75


def test_replay_frame_uses_dynamic_flow_layout() -> None:
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    if QApplication.instance() is None:
        QApplication([])

    layout = Layout.__new__(Layout)
    layout.main_window = _FakeMainWindow()
    layout.text_area = QWidget()
    layout.text_area_layout = QVBoxLayout(layout.text_area)

    frame = Layout.replay_frame.func(layout)

    assert isinstance(frame.layout(), _FlowLayout)
    assert frame.minimumHeight() == tuney.ui.layout.REPLAY_FRAME_HEIGHT
    assert frame.minimumHeight() != frame.maximumHeight()


def test_loop_tempo_accepts_values_below_one() -> None:
    from PySide6.QtWidgets import (
        QApplication,
        QDoubleSpinBox,
        QLabel,
        QVBoxLayout,
        QWidget,
    )

    if QApplication.instance() is None:
        QApplication([])

    layout = Layout.__new__(Layout)
    layout.main_window = _FakeMainWindow()
    layout.text_area = QWidget()
    layout.text_area_layout = QVBoxLayout(layout.text_area)

    frame = Layout.loop_controls.func(layout)
    spin = frame.findChild(QDoubleSpinBox)

    assert spin is not None
    assert spin.minimum() < 1.0
    assert spin.decimals() == 2
    clock = frame.findChild(QLabel, 'loop_clock')

    assert clock is not None
    assert clock.text() == '0:00.0'

    layout.set_loop_clock(65_432)

    assert clock.text() == '1:05.4'

    spin.setValue(0.5)
    spin.editingFinished.emit()

    assert layout.main_window.loop_tempos == [0.5]


def test_loop_controls_use_dynamic_flow_layout() -> None:
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    if QApplication.instance() is None:
        QApplication([])

    layout = Layout.__new__(Layout)
    layout.main_window = _FakeMainWindow()
    layout.text_area = QWidget()
    layout.text_area_layout = QVBoxLayout(layout.text_area)

    frame = Layout.loop_controls.func(layout)

    assert isinstance(frame.layout(), _FlowLayout)
    assert frame.minimumHeight() == tuney.ui.layout.LOOP_CONTROLS_HEIGHT
    assert frame.minimumHeight() != frame.maximumHeight()


def test_finish_startup_layout_reveals_after_deferred_build() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QWidget

    if QApplication.instance() is None:
        QApplication([])

    calls: list[str] = []
    layout = Layout.__new__(Layout)
    QWidget.__init__(layout)
    layout.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    layout.hide()
    layout.setEnabled(False)
    layout.control_panel = _FakeStartupControlPanel(calls)
    layout.root = _FakeStartupRoot(calls)
    layout.splitter = _FakeStartupSplitter(calls)
    layout.main_window = _FakeStartupMainWindow(calls)
    layout.rebuild_note_grid = lambda: calls.append('grid')
    layout.refresh_note_button_fonts = lambda: calls.append('fonts')

    Layout.finish_startup_layout(layout)

    assert calls == [
        'control_panel',
        'grid',
        'root',
        'splitter',
        'events',
        'fonts',
        'focus',
    ]
    assert layout.isEnabled()
    assert not layout.isHidden()


def test_note_font_refresh_is_debounced_during_resize(monkeypatch) -> None:
    callbacks = []
    calls = []
    layout = Layout.__new__(Layout)
    layout._note_font_refresh_pending = False
    layout.refresh_note_button_fonts = lambda: calls.append('fonts')
    monkeypatch.setattr(
        tuney.ui.layout.QTimer,
        'singleShot',
        lambda delay, callback: callbacks.append((delay, callback)),
    )

    layout.schedule_note_button_font_refresh()
    layout.schedule_note_button_font_refresh()

    assert len(callbacks) == 1
    assert callbacks[0][0] == tuney.ui.layout.NOTE_FONT_REFRESH_DELAY_MS
    assert calls == []

    callbacks[0][1]()

    assert calls == ['fonts']
    assert not layout._note_font_refresh_pending


class _FakeScale:
    note_count = 1

    @staticmethod
    def frequency(_: object, note_number: int) -> float:
        return 440 * 2 ** ((note_number - 69) / 12)


class _FakeMapper:
    char_to_number = {'a': 69, 'b': 70}


class _FakeApp:
    def __init__(self) -> None:
        self.labels = {'a': 'A', 'b': 'B'}
        self.mapper = _FakeMapper()
        self.scale = _FakeScale()
        self.sound = _FakeSound()
        self.hover_time = 1.0
        self.tuning = object()

    @staticmethod
    def on_char(_: object) -> None:
        pass

    @property
    def note_labels(self) -> dict[str, str]:
        return self.labels


class _FakeMainWindow:
    def __init__(self) -> None:
        self.app = _FakeApp()
        self.columns = 1
        self.rows = 1
        self.master_gains: list[float] = []
        self.loop_tempos: list[float] = []
        self.minimum_content_height = 0
        self.enforce_minimum_size_count = 0
        self.history = _FakeHistory()

    @property
    def current_theme(self):
        return tuney.ui.theme.LIGHT_THEME

    def on_transport_state(self, *_: object) -> bool:
        return True

    def on_replay(self) -> None:
        pass

    def on_randomize_timing(self) -> None:
        pass

    def on_loop_replay(self, _: bool) -> None:
        pass

    def on_randomize_on_each_loop(self, _: bool) -> None:
        pass

    def on_help(self) -> None:
        pass

    def on_master_gain(self, gain: float) -> None:
        self.master_gains.append(gain)

    def on_loop_before(self, _: str) -> None:
        pass

    def on_loop_after(self, _: str) -> None:
        pass

    def on_loop_tempo(self, tempo: float) -> None:
        self.loop_tempos.append(tempo)

    def enforce_minimum_size(self) -> None:
        self.enforce_minimum_size_count += 1


class _FakeResizeWindow:
    def __init__(self, width: int, height: int, minimum_content_height: int) -> None:
        self._width = width
        self._height = height
        self.minimum_content_height = minimum_content_height
        self.sizes: list[tuple[int, int]] = []

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def resize(self, width: int, height: int) -> None:
        self.sizes.append((width, height))
        self._width = width
        self._height = height

    def schedule_minimum_size_enforcement(self) -> None:
        self._minimum_size_timer.start(
            tuney.ui.main_window.MINIMUM_SIZE_ENFORCEMENT_DELAY_IN_MS
        )

    def enforce_minimum_size(self) -> None:
        width = max(self.width(), tuney.ui.main_window.MIN_PROGRAM_WIDTH)
        height = max(self.height(), self.minimum_content_height)
        if width != self.width() or height != self.height():
            self.resize(width, height)


class _FakeMinimumSizeTimer:
    def __init__(self) -> None:
        self.delays: list[int] = []

    def start(self, delay: int) -> None:
        self.delays.append(delay)


class _FakePressedApplication:
    @staticmethod
    def mouseButtons() -> tuney.ui.main_window.Qt.MouseButton:
        return tuney.ui.main_window.Qt.MouseButton.LeftButton


class _FakeReleasedApplication:
    @staticmethod
    def mouseButtons() -> tuney.ui.main_window.Qt.MouseButton:
        return tuney.ui.main_window.Qt.MouseButton.NoButton


class _FakeMenuHistory:
    def undo(self) -> None:
        pass

    def redo(self) -> None:
        pass


class _FakeMenuApp:
    def __init__(self, theme: tuney.ui.theme.ThemeName) -> None:
        self.global_config = GlobalConfig(theme=theme)
        self.show_text_timings = False
        self.load_autosave = True

    def randomize_settings(self) -> None:
        pass


class _FakeMenuWindow:
    def __init__(self, theme: tuney.ui.theme.ThemeName) -> None:
        from PySide6.QtWidgets import QMainWindow

        self._window = QMainWindow()
        self.app = _FakeMenuApp(theme)
        self.history = _FakeMenuHistory()

    def menuBar(self):
        return self._window.menuBar()

    def _update_export_tuning_action(self) -> None:
        pass

    @property
    def current_theme(self):
        return tuney.ui.theme.theme_for_name(self.app.global_config.theme)

    def __getattr__(self, name: str):
        if name.startswith('on_'):
            return lambda *_: None
        raise AttributeError(name)


class _FakeThemeUi:
    def __init__(self, window: object) -> None:
        self.window = window

    def refresh_theme(self) -> None:
        self.window.refresh_count += 1


class _FakeThemeApp:
    def __init__(self, config: GlobalConfig) -> None:
        self.global_config = config


class _FakeThemeWindow:
    def __init__(self, config: GlobalConfig, qt_app: object) -> None:
        self.app = _FakeThemeApp(config)
        self.qt_app = qt_app
        self.ui = _FakeThemeUi(self)
        self.refresh_count = 0
        self.sync_count = 0

    @property
    def current_theme(self):
        return tuney.ui.theme.theme_for_name(self.app.global_config.theme)

    def sync_config_actions(self) -> None:
        self.sync_count += 1


class _FakeSplitter:
    handle_width = 26

    def handleWidth(self) -> int:
        return self.handle_width


class _FakeHistory:
    loop_before = 0.0
    loop_after = 0.0
    loop_tempo = 1.0


class _FakeSound:
    master_gain = 1.2345


class _FakeStartupControlPanel:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def rebuild(self) -> None:
        self.calls.append('control_panel')


class _FakeStartupRoot:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def activate(self) -> None:
        self.calls.append('root')


class _FakeStartupSplitter:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def updateGeometry(self) -> None:
        self.calls.append('splitter')


class _FakeStartupQtApp:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def processEvents(self) -> None:
        self.calls.append('events')


class _FakeStartupMainWindow:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.qt_app = _FakeStartupQtApp(calls)

    def setFocus(self, _: object) -> None:
        self.calls.append('focus')


class _FakeCursor:
    position: int | None = None

    def setPosition(self, position: int) -> None:
        self.position = position


class _FakeTextBox:
    def __init__(self, text: str) -> None:
        self.text = text
        self.cursor = _FakeCursor()
        self.clear_focus_count = 0
        self.focus_count = 0

    def clearFocus(self) -> None:
        self.clear_focus_count += 1

    def toPlainText(self) -> str:
        return self.text

    def textCursor(self) -> _FakeCursor:
        return self.cursor

    def setTextCursor(self, cursor: _FakeCursor) -> None:
        self.cursor = cursor

    def ensureCursorVisible(self) -> None:
        pass

    def setFocus(self, _: object) -> None:
        self.focus_count += 1


class _FakeTextStack:
    def __init__(self, widget: object) -> None:
        self.widget = widget

    def currentWidget(self) -> object:
        return self.widget
