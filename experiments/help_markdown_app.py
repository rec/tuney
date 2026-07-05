from __future__ import annotations

import html
import re
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

README = Path(__file__).resolve().parents[1] / 'README.md'
help_dialog: QDialog | None = None
LINK_RE = re.compile(r'\[([^]]+)]\(([^)]+)\)')


def main() -> None:
    app = QApplication([])
    window = QWidget()
    window.setWindowTitle('Help rendering test')

    readme_button = QPushButton('Show README.md without emoji', window)
    readme_button.clicked.connect(partial(show_readme, window))

    emoji_button = QPushButton('Show emoji test', window)
    emoji_button.clicked.connect(partial(show_emoji_test, window))

    layout = QVBoxLayout(window)
    layout.addWidget(readme_button)
    layout.addWidget(emoji_button)

    window.resize(300, 110)
    window.show()
    app.exec()


def show_readme(parent: QWidget) -> None:
    global help_dialog

    dialog = QDialog(parent)
    dialog.setWindowTitle('README.md')

    text = QTextBrowser(dialog)
    text.setHtml(markdown_to_html(README.read_text()))
    text.setOpenExternalLinks(True)

    close = QPushButton('Close', dialog)
    close.clicked.connect(dialog.close)

    layout = QVBoxLayout(dialog)
    layout.addWidget(text)
    layout.addWidget(close)

    dialog.resize(720, 520)
    help_dialog = dialog
    dialog.show()


def show_emoji_test(parent: QWidget) -> None:
    global help_dialog

    dialog = QDialog(parent)
    dialog.setWindowTitle('Emoji rendering test')

    text = QTextBrowser(dialog)
    text.setHtml(
        '<h1>Emoji rendering test</h1>'
        '<p>If this window stays open, QTextBrowser can render these emoji:</p>'
        '<p style="font-size: 24px;">'
        '🎵 '
        #        '🎶 '
        #        '😀 '
        #        '✅ '
        '</p>'
    )

    close = QPushButton('Close', dialog)
    close.clicked.connect(dialog.close)

    layout = QVBoxLayout(dialog)
    layout.addWidget(text)
    layout.addWidget(close)

    dialog.resize(420, 260)
    help_dialog = dialog
    dialog.show()


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


if __name__ == '__main__':
    main()
