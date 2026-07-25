from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tuney.ui.control_panel_layout import _FlowLayout
from tuney.ui.splitter import SpacedSplitter


def main(argv: Sequence[str] | None = None) -> None:
    options = _parser().parse_args(argv)
    qt_app = QApplication(sys.argv[:1])
    window = ResizeRepro(options)
    window.show()
    sys.exit(qt_app.exec())


class ResizeRepro(QMainWindow):
    def __init__(self, options: argparse.Namespace) -> None:
        super().__init__()
        self.options = options
        self.setWindowTitle('Tuney resize repro')
        self.setCentralWidget(self._main_widget())
        self.resize(640, 720)

    def resizeEvent(self, event: QResizeEvent) -> None:
        if self.options.log_resize:
            size = event.size()
            old = event.oldSize()
            print(
                f'resize old={old.width()}x{old.height()} '
                f'new={size.width()}x{size.height()}'
            )
        super().resizeEvent(event)

    def _main_widget(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._splitter(), stretch=1)
        return widget

    def _splitter(self) -> QSplitter:
        if self.options.splitter == 'spaced':
            splitter = SpacedSplitter(
                Qt.Orientation.Vertical,
                self,
                handle_size=6,
                space_above=10,
                space_below=10,
            )
        else:
            splitter = QSplitter(Qt.Orientation.Vertical, self)
            splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._control_panel())
        splitter.addWidget(self._text_area())
        if self.options.notes:
            splitter.addWidget(self._note_grid())
        splitter.setSizes([270, 200, 260])
        return splitter

    def _control_panel(self) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        if self.options.panel == 'flow':
            layout = _FlowLayout(content)
            for i in range(self.options.controls):
                layout.addWidget(_control_cell(content, i))
        elif self.options.panel == 'grid':
            layout = QGridLayout(content)
            layout.setContentsMargins(6, 6, 6, 6)
            for i in range(self.options.controls):
                layout.addWidget(_control_cell(content, i), i // 3, i % 3)
        else:
            layout = QVBoxLayout(content)
            layout.addWidget(QLabel('empty control panel', content))
            layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _text_area(self) -> QWidget:
        frame = QWidget(self)
        layout = QVBoxLayout(frame)
        label = QLabel('Text:', frame)
        layout.addWidget(label)
        text = QTextEdit(frame)
        text.setPlainText('Resize diagonally from the lower-right corner.\n' * 10)
        layout.addWidget(text, stretch=1)
        buttons = QWidget(frame)
        button_layout = QHBoxLayout(buttons)
        for name in ('Record', 'Play', 'Loop', 'Randomize time', '?'):
            button_layout.addWidget(QPushButton(name, buttons))
        layout.addWidget(buttons)
        return frame

    def _note_grid(self) -> QWidget:
        frame = QWidget(self)
        layout = QGridLayout(frame)
        columns = max(1, round(self.options.notes**0.5))
        for i in range(self.options.notes):
            button = QPushButton(chr(ord('A') + i % 26), frame)
            button.setMinimumSize(50, 30)
            layout.addWidget(button, i // columns, i % columns)
        return frame


def _control_cell(parent: QWidget, index: int) -> QWidget:
    frame = QWidget(parent)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(3, 3, 3, 3)
    layout.addWidget(QLabel(f'Field {index}', frame))
    if index % 3 == 0:
        entry = QLineEdit(frame)
        entry.setText(str(index))
        layout.addWidget(entry)
    elif index % 3 == 1:
        combo = QComboBox(frame)
        combo.addItems(['alpha', 'beta', 'gamma'])
        layout.addWidget(combo)
    else:
        layout.addWidget(QCheckBox('Enabled', frame))
    return frame


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--splitter', choices=['spaced', 'standard'], default='spaced')
    parser.add_argument('--panel', choices=['flow', 'grid', 'empty'], default='flow')
    parser.add_argument('--controls', type=int, default=180)
    parser.add_argument('--notes', type=int, default=52)
    parser.add_argument('--log-resize', action='store_true')
    return parser


if __name__ == '__main__':
    main()
