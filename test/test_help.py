from __future__ import annotations

import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QWidget

from tuney.ui.help import README, _help_dialog, markdown_to_html, read_help_markdown


def test_help_markdown_uses_bundled_readme(tmp_path, monkeypatch) -> None:
    help_text = '# Bundled help'
    (tmp_path / README).write_text(help_text)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)

    assert read_help_markdown() == help_text


def test_markdown_to_html_handles_readme_subset() -> None:
    assert markdown_to_html(
        '# Tuney 🎵\n\n'
        'See [docs](https://example.com) and `tuney --help`.\n'
        'Escape <this>.\n\n'
        '## Install\n'
    ) == (
        '<h1>Tuney </h1>'
        '<p>See <a href="https://example.com">docs</a> and '
        '<code>tuney --help</code>. Escape &lt;this&gt;.</p>'
        '<h2>Install</h2>'
    )


def test_help_dialog_has_standard_close_shortcut() -> None:
    _ = QApplication.instance() or QApplication([])
    parent = QWidget()
    dialog = _help_dialog(parent)

    shortcuts = dialog.findChildren(QShortcut)

    assert any(QKeySequence.StandardKey.Close in s.keys() for s in shortcuts)
