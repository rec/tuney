import pytest

from tuney.scale.ratios import Ratios
from tuney.scale.tuning import Computed, Tuning


def test_tuning_uses_table_when_present() -> None:
    assert Tuning(tuning=[440])(0) == 440


def test_tuning_uses_computed_by_default() -> None:
    assert Tuning()(69) == 440


def test_tuning_uses_ratios_when_present() -> None:
    assert Tuning(tuning=Ratios(ratios=[2]))(70) == 880


def test_computed_exports_one_octave_of_ratios() -> None:
    assert Computed(notes_per_octave=3, octave_ratio=8).as_ratios().ratios == (
        pytest.approx([2, 4, 8])
    )
