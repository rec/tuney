from tuney.ui.layout import Layout


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
