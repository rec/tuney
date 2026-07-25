from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def main(argv: Sequence[str] | None = None) -> None:
    options = _parser().parse_args(argv)
    qt_app = QApplication(sys.argv[:1])
    if options.style:
        qt_app.setStyle(options.style)
    print(f'PySide6 {pyside_version}, style {qt_app.style().objectName()}')
    if options.mode in {'bare-widget', 'label-widget', 'widget'}:
        window = _widget_window(options)
        window.setWindowTitle('Pure PySide QWidget resize repro')
        window.resize(640, 720)
        window.show()
    else:
        window = ResizeRepro(options)
        window.show()
    sys.exit(qt_app.exec())


class ResizeRepro(QMainWindow):
    def __init__(self, options: argparse.Namespace) -> None:
        super().__init__()
        self.options = options
        self.setWindowTitle('Pure PySide QMainWindow resize repro')
        if options.mode != 'empty-main-window':
            self.setCentralWidget(_widget_window(options))
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


def _widget_window(options: argparse.Namespace) -> QWidget:
    widget = QWidget()
    if options.mode == 'bare-widget':
        return widget
    if options.mode == 'label-widget':
        label = QLabel('Pure PySide top-level label', widget)
        label.move(20, 20)
        return widget
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    if options.mode == 'layout':
        layout.addStretch()
    elif options.mode == 'text':
        text = QTextEdit(widget)
        text.setPlainText('Resize diagonally from the lower-right corner.\n' * 10)
        layout.addWidget(text)
    elif options.mode == 'buttons':
        grid = QWidget(widget)
        grid_layout = QGridLayout(grid)
        for i in range(options.buttons):
            grid_layout.addWidget(
                QPushButton(chr(ord('A') + i % 26), grid),
                i // 8,
                i % 8,
            )
        layout.addWidget(grid)
    else:
        label = QLabel('Pure PySide blank window', widget)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
    return widget


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--mode',
        choices=[
            'empty-main-window',
            'bare-widget',
            'label-widget',
            'layout',
            'blank',
            'widget',
            'buttons',
            'text',
        ],
        default='blank',
    )
    parser.add_argument('--buttons', type=int, default=52)
    parser.add_argument('--style')
    parser.add_argument('--log-resize', action='store_true')
    return parser


if __name__ == '__main__':
    main()
