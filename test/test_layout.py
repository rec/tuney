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
    layout.__dict__['note_button_cache'] = {}

    layout.rebuild_note_grid()
    first_a = layout.note_buttons['a']
    first_b = layout.note_buttons['b']

    layout.main_window.app.labels = {'a': 'A2'}
    layout.rebuild_note_grid()

    assert layout.note_buttons == {'a': first_a}
    assert layout.note_buttons['a'].note_name == 'A2'
    assert first_b.isHidden()
    assert first_b.parent() is layout.note_grid_widget


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
        'fonts',
        'events',
        'fonts',
        'focus',
    ]
    assert layout.isEnabled()
    assert not layout.isHidden()


class _FakeScale:
    note_count = 1


class _FakeApp:
    def __init__(self) -> None:
        self.labels = {'a': 'A', 'b': 'B'}
        self.scale = _FakeScale()
        self.sound = _FakeSound()
        self.hover_time = 1.0

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
        self.history = _FakeHistory()

    def on_transport_state(self, *_: object) -> bool:
        return True

    def on_replay(self) -> None:
        pass

    def on_randomize_timing(self) -> None:
        pass

    def on_loop_replay(self, _: bool) -> None:
        pass

    def on_master_gain(self, gain: float) -> None:
        self.master_gains.append(gain)

    def on_loop_before(self, _: str) -> None:
        pass

    def on_loop_after(self, _: str) -> None:
        pass

    def on_loop_tempo(self, tempo: float) -> None:
        self.loop_tempos.append(tempo)

    def on_randomize_on_each_loop(self, _: bool) -> None:
        pass

    def on_help(self) -> None:
        pass


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
