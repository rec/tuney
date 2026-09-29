from pathlib import Path

import pytest

from tuney.scale.ratios import Ratios

SCALE_DIR = Path('test/scales')
SCALA_FILES = (
    'partch-barstow.scl',
    'pelog1.scl',
    'turkish_17.scl',
)


@pytest.mark.parametrize('filename', SCALA_FILES)
def test_scala_files_round_trip(filename: str, tmp_path) -> None:
    ratios = Ratios.read_scala_file(SCALE_DIR / filename)
    path = tmp_path / filename

    ratios.write_scala_file(path)
    round_trip = Ratios.read_scala_file(path)

    assert round_trip.name == filename
    assert round_trip.desc == ratios.desc
    assert round_trip.length == ratios.length
    assert len(round_trip.ratios) == len(ratios.ratios)
    assert [float(r) for r in round_trip.ratios] == pytest.approx(
        [float(r) for r in ratios.ratios],
        abs=1e-8,
    )


def test_failed_scala_export_preserves_existing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / 'scale.scl'
    destination.write_text('original')
    write_text = Path.write_text

    def fail_after_partial_write(
        self: Path, data: str, encoding: str = 'latin-1'
    ) -> int:
        write_text(self, data[:8], encoding=encoding)
        raise OSError('disk full')

    monkeypatch.setattr(Path, 'write_text', fail_after_partial_write)
    with pytest.raises(OSError, match='disk full'):
        Ratios(text='2').write_scala_file(destination)

    assert destination.read_text() == 'original'
    assert list(tmp_path.iterdir()) == [destination]
