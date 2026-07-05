from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout, QWidget

HELP_TITLE = 'Tuney Help'
README = 'README.md'
LINK_RE = re.compile(r'\[([^]]+)]\(([^)]+)\)')


def show_help(parent: QWidget) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(HELP_TITLE)

    text = QTextBrowser(dialog)
    text.setHtml(markdown_to_html(read_help_markdown()))
    text.setOpenExternalLinks(True)

    close = QPushButton('Close', dialog)
    close.clicked.connect(dialog.close)

    layout = QVBoxLayout(dialog)
    layout.addWidget(text)
    layout.addWidget(close)

    dialog.resize(720, 520)
    dialog.exec()


def read_help_markdown() -> str:
    if (path := _readme_path()) is None:
        return '# Tuney\n\nREADME.md was not found.'
    return path.read_text()


def markdown_to_html(markdown: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f'<p>{" ".join(paragraph)}</p>')
            paragraph.clear()

    for line in markdown.splitlines():
        if not line:
            flush_paragraph()
        elif line.startswith('## '):
            flush_paragraph()
            blocks.append(f'<h2>{_inline_markdown(line[3:])}</h2>')
        elif line.startswith('# '):
            flush_paragraph()
            blocks.append(f'<h1>{_inline_markdown(line[2:])}</h1>')
        else:
            paragraph.append(_inline_markdown(line))
    flush_paragraph()
    return ''.join(blocks)


def _inline_markdown(text: str) -> str:
    escaped = html.escape(_strip_emoji(text))
    escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
    return LINK_RE.sub(r'<a href="\2">\1</a>', escaped)


def _strip_emoji(text: str) -> str:
    return ''.join(char for char in text if ord(char) < 0x1F300)


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
