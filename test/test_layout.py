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


class _FakeScale:
    note_count = 1


class _FakeApp:
    def __init__(self) -> None:
        self.labels = {'a': 'A', 'b': 'B'}
        self.scale = _FakeScale()

    @property
    def note_labels(self) -> dict[str, str]:
        return self.labels


class _FakeMainWindow:
    def __init__(self) -> None:
        self.app = _FakeApp()
        self.columns = 1
        self.rows = 1


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
