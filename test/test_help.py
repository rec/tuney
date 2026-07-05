from __future__ import annotations

import sys
from pathlib import Path

from pytest import MonkeyPatch

from tuney.ui.help import README, markdown_to_html, read_help_markdown


def test_help_markdown_uses_bundled_readme(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
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
