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
def test_scala_files_round_trip(filename: str, tmp_path: Path) -> None:
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
