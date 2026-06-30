from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout, QWidget

HELP_TITLE = 'Tuney Help'
README = 'README.md'


def show_help(parent: QWidget) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(HELP_TITLE)

    text = QTextBrowser(dialog)
    text.setMarkdown(read_help_markdown())
    text.setOpenExternalLinks(True)

    close = QPushButton('Close', dialog)
    close.clicked.connect(dialog.close)

    layout = QVBoxLayout(dialog)
    layout.addWidget(text)
    layout.addWidget(close)

    dialog.resize(720, 520)
    dialog.exec()


def read_help_markdown() -> str:
    path = _readme_path()
    if path is None:
        return '# Tuney\n\nREADME.md was not found.'
    return path.read_text()


def _readme_path() -> Path | None:
    for path in _readme_paths():
        if path.exists():
            return path
    return None


def _readme_paths() -> list[Path]:
    paths = [Path(__file__).resolve().parents[2] / README]
    if bundle_root := getattr(sys, '_MEIPASS', None):
        paths.insert(0, Path(bundle_root) / README)
    return paths
