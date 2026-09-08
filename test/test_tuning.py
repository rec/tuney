import pytest

from tuney.scale.ratios import Ratios
from tuney.scale.table import Table
from tuney.scale.tuning import Computed, Tuning, Type


def test_tuning_uses_table_when_present() -> None:
    assert Tuning(type=Type.table, table=Table(text='440'))(0) == 440


def test_tuning_uses_computed_by_default() -> None:
    assert Tuning()(69) == 440


def test_computed_tuning_rejects_zero_notes_per_octave() -> None:
    with pytest.raises(ValueError, match='greater than 0'):
        Computed(notes_per_octave=0)


def test_empty_frequency_table_reports_configuration_error() -> None:
    with pytest.raises(ValueError, match='No frequency table configured'):
        Tuning(type=Type.table, table=Table())(69)


def test_empty_ratios_report_configuration_error() -> None:
    with pytest.raises(ValueError, match='No tuning ratios configured'):
        Ratios()


@pytest.mark.parametrize(
    ('tuning', 'message'),
    [
        (Table(text='0'), 'Frequency table values must be positive'),
        (Ratios(text='0'), 'Tuning ratios must be positive'),
    ],
)
def test_tuning_sources_require_positive_values(
    tuning: Table | Ratios, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        tuning(0)


def test_tuning_uses_ratios_when_present() -> None:
    assert Tuning(type=Type.ratios, ratios=Ratios(text='2'))(70) == 880


def test_tuning_keeps_inactive_values() -> None:
    tuning = Tuning(
        type=Type.table,
        computed=Computed(notes_per_octave=19),
        table=Table(text='440'),
        ratios=Ratios(text='3; 2'),
    )

    assert tuning(0) == 440
    assert tuning.computed == Computed(notes_per_octave=19)
    assert tuning.ratios == Ratios(text='3; 2')


def test_computed_exports_one_octave_of_ratios() -> None:
    assert Computed(notes_per_octave=3, octave_ratio=8).as_ratios().ratios == (
        pytest.approx([2, 4, 8])
    )


def test_table_is_finite_but_tuney_keeps_notes_in_instrument_range() -> None:
    table = Table(text='440; 660')
    assert table(0) == 440
    assert table(1) == 660
    for note in (-1, 2):
        with pytest.raises(ValueError, match='outside'):
            table(note)
    tuning = Tuning(type=Type.table, table=table)
    assert tuning(68) == 660
    assert tuning(71) == 440
    assert tuning.definition(69) == 440
    with pytest.raises(ValueError, match='outside'):
        tuning.definition(71)


def test_fractional_and_power_authoring_compiles_to_shared_ratios() -> None:
    ratios = Ratios(text='5/4; 2^(1/2); 2')
    assert ratios.definition.values[1] == '5/4'
    assert ratios(2) == pytest.approx(2**0.5)
    assert ratios(4) == 2.5


def test_edits_to_computed_configuration_update_shared_pitch_resolution() -> None:
    computed = Computed()
    tuning = Tuning(computed=computed)
    original = tuning(70)
    computed.notes_per_octave = 24
    assert tuning(70) != original
    assert tuning(71) == pytest.approx(original)
