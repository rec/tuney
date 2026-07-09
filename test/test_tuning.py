import pytest

from tuney.scale.ratios import Ratios
from tuney.scale.tuning import Computed, Tuning, Type


def test_tuning_uses_table_when_present() -> None:
    assert Tuning(type=Type.table, table=[440])(0) == 440


def test_tuning_uses_computed_by_default() -> None:
    assert Tuning()(69) == 440


def test_tuning_uses_ratios_when_present() -> None:
    assert Tuning(type=Type.ratios, ratios=Ratios(ratios=[2]))(70) == 880


def test_tuning_keeps_inactive_values() -> None:
    tuning = Tuning(
        type=Type.table,
        computed=Computed(notes_per_octave=19),
        table=[440],
        ratios=Ratios(ratios=[3, 2]),
    )

    assert tuning(0) == 440
    assert tuning.computed == Computed(notes_per_octave=19)
    assert tuning.ratios == Ratios(ratios=[3, 2])


def test_computed_exports_one_octave_of_ratios() -> None:
    assert Computed(notes_per_octave=3, octave_ratio=8).as_ratios().ratios == (
        pytest.approx([2, 4, 8])
    )
