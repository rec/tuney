import pytest

from test.app_helpers import ensure_qt_app, stub_external_option_probes
from tuney.app.app import App
from tuney.config.tuney import Tuney
from tuney.scale.ratios import Ratios
from tuney.scale.scala_browser import build_trie
from tuney.scale.tuning import TuningSource
from tuney.ui import control_panel, control_panel_scala, control_panel_sizing

pytestmark = pytest.mark.usefixtures(stub_external_option_probes.__name__)


def test_scala_browser_navigates_existing_trie_nodes(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QWidget

    ratios = {
        'abc': Ratios(text='2', name='abc.scl', desc='first scale'),
        'abd': Ratios(text='3', name='abd.scl', desc='second scale'),
        'xyz': Ratios(text='4', name='xyz.scl', desc='third scale'),
    }
    monkeypatch.setattr(control_panel_scala, 'scala_trie', lambda: build_trie(ratios))

    ensure_qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None
    assert browser.text() == 'abc.scl'
    assert browser.cursorPosition() == 0
    assert browser.isReadOnly()
    assert browser.selectedText() == ''
    assert 'color: #909090;' in browser.styleSheet()

    _press(browser, Qt.Key.Key_A, 'a')
    _press(browser, Qt.Key.Key_X, 'x')
    _press(browser, Qt.Key.Key_B, 'b')
    _press(browser, Qt.Key.Key_Down)

    assert browser.text() == 'abd.scl'
    assert browser.selectionStart() == 2
    assert browser.selectedText() == 'd.scl'
    assert browser.toolTip() == ''

    _press(browser, Qt.Key.Key_Down)
    assert browser.text() == 'abc.scl'
    assert browser.selectedText() == 'c.scl'
    assert browser.toolTip() == ''

    _press(browser, Qt.Key.Key_Left)
    _press(browser, Qt.Key.Key_Up)
    assert browser.text() == 'xyz.scl'
    assert browser.selectionStart() == 0

    _press(browser, Qt.Key.Key_X, 'x')
    assert browser.text() == 'xyz.scl'
    assert browser.selectionStart() == 1
    assert browser.selectedText() == 'yz.scl'

    _press(browser, Qt.Key.Key_Down)
    assert browser.text() == 'xyz.scl'
    assert browser.selectionStart() == 1

    _press(browser, Qt.Key.Key_Right)
    assert browser.cursorPosition() == 7

    _press(browser, Qt.Key.Key_Left)
    assert browser.selectionStart() == 0
    assert browser.selectedText() == 'xyz.scl'


def test_scala_browser_is_in_tuning_section(monkeypatch) -> None:
    from PySide6.QtWidgets import QLineEdit, QToolButton, QWidget

    ratios = {'abc': Ratios(text='2', name='abc.scl', desc='first scale')}
    monkeypatch.setattr(control_panel_scala, 'scala_trie', lambda: build_trie(ratios))

    ensure_qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None

    section: object = browser
    while isinstance(section, QWidget) and section.objectName() != 'control_section':
        section = section.parentWidget()

    assert isinstance(section, QWidget)
    button = section.findChild(QToolButton, 'control_section_disclosure')
    assert button is not None
    assert button.text() == 'Tuning'


def test_scala_description_does_not_force_panel_width() -> None:
    from PySide6.QtWidgets import QLineEdit, QSizePolicy, QWidget

    ensure_qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    description = panel.findChild(QLineEdit, 'tuning_description')

    assert description is not None
    assert description.minimumWidth() == control_panel_sizing.MIN_EDITOR_WIDTH
    assert description.maximumWidth() == 120 * control_panel_sizing.ENTRY_CHAR_WIDTH
    assert description.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding


def test_scala_browser_auditions_completed_tuning(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QWidget

    ratios = Ratios(text='3/2', name='abc.scl', desc='first scale')
    app = App(gui=True)
    original = app.tuning.model_copy(deep=True)
    closed = []
    app.__dict__['main_window'] = _FakeMainWindow()
    app.__dict__['player'] = _FakePlayer(closed)
    other_ratios = Ratios(text='2', name='xbc.scl', desc='second scale')
    monkeypatch.setattr(
        control_panel_scala,
        'scala_trie',
        lambda: build_trie({'abc': ratios, 'xbc': other_ratios}),
    )

    ensure_qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, app, app=app)
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None

    _press(browser, Qt.Key.Key_A, 'a')
    _press(browser, Qt.Key.Key_B, 'b')
    _press(browser, Qt.Key.Key_C, 'c')

    assert app.tuning.type == TuningSource.ratios
    assert app.tuning.ratios == ratios
    assert closed == ['close']
    assert 'player' not in app.__dict__

    _press(browser, Qt.Key.Key_Left)

    assert app.tuning.model_dump() == original.model_dump()
    assert closed == ['close']


def test_scala_browser_loads_selected_tuning_with_undo(monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QMessageBox, QWidget

    ratios = Ratios(text='3/2', name='abc.scl', desc='first scale')
    app = App(gui=True)
    app.__dict__['main_window'] = _FakeMainWindow()
    monkeypatch.setattr(
        control_panel_scala, 'scala_trie', lambda: build_trie({'abc': ratios})
    )
    monkeypatch.setattr(
        control_panel.QtWidgets.QMessageBox,
        'question',
        lambda *_: QMessageBox.StandardButton.Yes,
    )

    ensure_qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, app, app=app)
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None
    name = panel.findChild(QLineEdit, 'tuning_name')
    description = panel.findChild(QLineEdit, 'tuning_description')
    assert name is not None
    assert description is not None

    _press(browser, Qt.Key.Key_A, 'a')
    _press(browser, Qt.Key.Key_B, 'b')
    _press(browser, Qt.Key.Key_C, 'c')
    assert name.text() == ''
    assert description.text() == ''
    _press(browser, Qt.Key.Key_Return)

    assert app.tuning.type == TuningSource.ratios
    assert app.tuning.ratios == ratios
    assert app.main_window.history.undo_count == 1
    assert app.main_window.ui.rebuild_count == 1
    assert name.text() == 'abc.scl'
    assert description.text() == 'first scale'


def test_scala_browser_starts_with_first_scala_file(monkeypatch) -> None:
    from PySide6.QtWidgets import QLineEdit, QWidget

    calls = []
    ratios = Ratios(text='3/2', name='abc.scl', desc='first scale')
    monkeypatch.setattr(
        control_panel_scala,
        'scala_trie',
        lambda: calls.append('load') or build_trie({'abc': ratios}),
    )

    ensure_qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None
    assert calls == ['load', 'load']
    assert browser.text() == 'abc.scl'
    assert browser.cursorPosition() == 0
    assert browser.selectedText() == ''
    assert 'color: #909090;' in browser.styleSheet()


def test_scala_browser_keeps_current_tooltip_open_while_active(monkeypatch) -> None:
    from PySide6.QtCore import QEvent, QPoint, Qt
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

    ratios = {
        'abc': Ratios(text='2', name='abc.scl', desc='first scale'),
        'abd': Ratios(text='3', name='abd.scl', desc='second scale'),
    }
    monkeypatch.setattr(control_panel_scala, 'scala_trie', lambda: build_trie(ratios))

    ensure_qt_app()
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuney())
    browser = panel.findChild(QLineEdit, 'scala_browser')
    assert browser is not None
    tooltip = browser.findChild(QLabel, 'scala_browser_active_tooltip')
    assert tooltip is not None

    browser.focusInEvent(QFocusEvent(QEvent.Type.FocusIn))
    assert browser.toolTip() == ''
    assert tooltip.text() == 'first scale'
    assert not tooltip.isHidden()
    assert tooltip.pos() == browser.mapToGlobal(browser.rect().bottomLeft()) + QPoint(
        0, 10
    )

    _press(browser, Qt.Key.Key_A, 'a')
    _press(browser, Qt.Key.Key_B, 'b')
    _press(browser, Qt.Key.Key_Down)
    assert browser.toolTip() == ''
    assert tooltip.text() == 'second scale'
    assert not tooltip.isHidden()

    browser.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))
    assert tooltip.isHidden()


def _press(widget, key: object, text: str = '') -> None:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    assert isinstance(key, Qt.Key)
    widget.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            key,
            Qt.KeyboardModifier.NoModifier,
            text,
        )
    )


class _FakeHistory:
    def __init__(self) -> None:
        self.undo_count = 0

    def checkpoint_undo(self) -> None:
        self.undo_count += 1


class _FakeUi:
    def __init__(self) -> None:
        self.rebuild_count = 0

    def rebuild_control_panel(self) -> None:
        self.rebuild_count += 1


class _FakeMainWindow:
    def __init__(self) -> None:
        self.history = _FakeHistory()
        self.ui = _FakeUi()


class _FakePlayer:
    def __init__(self, closed: list[str]) -> None:
        self.closed = closed

    def close(self) -> None:
        self.closed.append('close')
