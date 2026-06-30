from __future__ import annotations

import sys
from pathlib import Path

from pytest import MonkeyPatch

from tuney.ui.help import README, read_help_markdown


def test_help_markdown_uses_bundled_readme(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    help_text = '# Bundled help'
    (tmp_path / README).write_text(help_text)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)

    assert read_help_markdown() == help_text
