from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def main(argv: Sequence[str] | None = None) -> None:
    options = _parser().parse_args(argv)
    qt_app = QApplication(sys.argv[:1])
    if options.style:
        qt_app.setStyle(options.style)
    print(
        f'PySide6 {pyside_version}, '
        f'Qt {qVersion()}, '
        f'style {qt_app.style().objectName()}, '
        f"LC_ALL={os.environ.get('LC_ALL')!r}, "
        f"LANG={os.environ.get('LANG')!r}, "
        f'window={options.window}'
    )
    if options.window == 'widget':
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
        if options.mode != 'empty':
            central = _widget_window(options)
            if options.central_ignored:
                central.setSizePolicy(
                    QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
                )
            self.setCentralWidget(central)
        if options.clear_window_minimum:
            self.setMinimumSize(0, 0)
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
    if options.mode == 'empty':
        return widget
    if options.mode == 'min-widget':
        widget.setMinimumSize(120, 40)
        return widget
    if options.mode == 'label-widget':
        label = QLabel('Pure PySide top-level label', widget)
        label.move(20, 20)
        return widget
    if options.mode == 'min-child-widget':
        child = QWidget(widget)
        child.setMinimumSize(120, 40)
        child.move(20, 20)
        return widget
    layout = QVBoxLayout(widget)
    if options.no_layout_constraint:
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
    layout.setContentsMargins(6, 6, 6, 6)
    if options.mode == 'layout':
        layout.addStretch()
    elif options.mode == 'layout-parent-min':
        widget.setMinimumSize(120, 40)
        layout.addStretch()
    elif options.mode == 'layout-parent-fixed':
        widget.setFixedSize(120, 40)
        layout.addStretch()
    elif options.mode == 'layout-empty-widget':
        layout.addWidget(QWidget(widget))
    elif options.mode == 'layout-min-empty-widget':
        child = QWidget(widget)
        child.setMinimumSize(120, 40)
        layout.addWidget(child)
    elif options.mode == 'layout-fixed-empty-widget':
        child = QWidget(widget)
        child.setFixedSize(120, 40)
        layout.addWidget(child)
    elif options.mode == 'layout-fixed-zero-widget':
        child = QWidget(widget)
        child.setFixedSize(0, 0)
        layout.addWidget(child)
    elif options.mode == 'layout-hidden-label':
        label = QLabel('Pure PySide hidden label in layout', widget)
        label.hide()
        layout.addWidget(label)
    elif options.mode == 'layout-empty-label':
        layout.addWidget(QLabel('', widget))
    elif options.mode == 'layout-label':
        layout.addWidget(QLabel('Pure PySide label in layout', widget))
    elif options.mode == 'layout-label-ignored':
        label = QLabel('Pure PySide ignored label in layout', widget)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        layout.addWidget(label)
    elif options.mode == 'layout-label-min-zero':
        label = QLabel('Pure PySide min-zero label in layout', widget)
        label.setMinimumSize(0, 0)
        layout.addWidget(label)
    elif options.mode == 'layout-label-pixmapless':
        label = QLabel(widget)
        label.setFixedSize(120, 40)
        layout.addWidget(label)
    elif options.mode == 'layout-label-centered':
        label = QLabel('Pure PySide centered label in layout', widget)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
    elif options.mode == 'layout-label-widget':
        layout.addWidget(QLabel('Pure PySide top-level label in layout', widget))
    elif options.mode == 'layout-button':
        layout.addWidget(QPushButton('Pure PySide button in layout', widget))
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
            'empty',
            'min-widget',
            'label-widget',
            'min-child-widget',
            'layout',
            'layout-parent-min',
            'layout-parent-fixed',
            'layout-empty-widget',
            'layout-min-empty-widget',
            'layout-fixed-empty-widget',
            'layout-fixed-zero-widget',
            'layout-hidden-label',
            'layout-empty-label',
            'layout-label',
            'layout-label-ignored',
            'layout-label-min-zero',
            'layout-label-pixmapless',
            'layout-label-centered',
            'layout-label-widget',
            'layout-button',
            'blank',
            'widget',
            'buttons',
            'text',
        ],
        default='blank',
    )
    parser.add_argument('--window', choices=['main', 'widget'], default='main')
    parser.add_argument('--buttons', type=int, default=52)
    parser.add_argument('--style')
    parser.add_argument('--log-resize', action='store_true')
    parser.add_argument('--no-layout-constraint', action='store_true')
    parser.add_argument('--central-ignored', action='store_true')
    parser.add_argument('--clear-window-minimum', action='store_true')
    return parser


if __name__ == '__main__':
    main()
