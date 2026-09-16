from pathlib import Path

import pytest

from tuney.app.app import App
from tuney.app.global_config import GlobalConfig
from tuney.presets import preset


@pytest.mark.parametrize('kind', ['toml', 'json', 'autosave', 'global', 'preset'])
def test_failed_save_preserves_previous_file(
    monkeypatch, tmp_path: Path, kind: str
) -> None:
    path = tmp_path / ('saved.json' if kind == 'json' else 'saved.toml')
    original = '{"text": "previous"}' if kind == 'json' else 'text = "previous"\n'
    path.write_text(original)
    monkeypatch.setattr(preset, 'USER_PRESETS', tmp_path)

    def fail(destination: Path, text: str) -> None:
        destination.write_bytes(b'partial')
        raise OSError('disk full')

    monkeypatch.setattr(Path, 'write_text', fail)
    with pytest.raises(OSError, match='disk full'):
        match kind:
            case 'toml' | 'json':
                App(text='new').save(path)
            case 'autosave':
                App(text='new').save_autosave(path)
            case 'global':
                GlobalConfig(file=path).save()
            case 'preset':
                preset.write_preset('saved', {'max_gap': 2})
    assert path.read_text() == original
    assert list(tmp_path.iterdir()) == [path]
