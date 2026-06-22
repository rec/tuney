import pytest

from test import twelve_tet as tt
from tuney.scale.accidentals import Accidentals
from tuney.scale.nearest_note import nearest_note
from tuney.scale.scale import Scale


def test_flat_sharp():
    actual = [''.join(i) for i in Scale().flats_sharps]
    expected = ['CD♭DE♭EFG♭GA♭AB♭B', 'CC♯DD♯EFF♯GG♯AA♯B']

    assert actual == expected


def test_accidentals_none_keeps_octave_steps_without_accidental_names() -> None:
    scale = Scale(accidentals=Accidentals.none)

    assert scale.note_count == 12
    assert scale.to_name(1) == 'C0'
    assert scale.to_number('C0') == 0
    assert scale._to_notes('C♯ D') == (['C', 'D'], ['♯'])
    with pytest.raises(ValueError, match='Bad number'):
        scale.to_number('C♯0')


def test_accidentals_half_adds_half_sharps_and_flats() -> None:
    scale = Scale(accidentals=Accidentals.half)

    assert [''.join(i) for i in scale.flats_sharps] == [
        'CDvDEvEFGvGAvABvB',
        'CC^DD^EFF^GG^AA^B',
    ]
    assert scale.to_number('C^0') == 1
    assert scale.to_number('Dv0') == 1


def test_accidentals_half_orders_larger_accidentals_before_smaller() -> None:
    scale = Scale(
        alphabet='CD',
        root='C',
        begin='C',
        end='D',
        intervals=[5, 5],
        accidentals='half',
    )

    assert [scale.to_name(i) for i in range(6)] == [
        'C0',
        'C^0',
        'C♯0',
        'D♭0',
        'Dv0',
        'D0',
    ]
    assert scale.to_number('C#0') == 2
    assert scale.to_number('D♭0') == 3


def test_accidentals_half_names_third_tones() -> None:
    scale = Scale(
        alphabet='CD',
        root='C',
        begin='C',
        end='D',
        intervals=[3, 3],
        accidentals=Accidentals.half,
    )

    assert [scale.to_name(i) for i in range(4)] == ['C0', 'C^0', 'Dv0', 'D0']
    assert [scale.to_name(i, use_sharp=False) for i in range(4)] == [
        'C0',
        'D♭0',
        'C♯0',
        'D0',
    ]


def test_white_notes():
    actual = [''.join(i) for i in Scale(notes='ABCDEFG').flats_sharps]
    expected = ['CDEFGAB', 'CDEFGAB']

    assert actual == expected


def test_interval_string_ignores_whitespace() -> None:
    assert Scale(intervals='221 2221').intervals == [2, 2, 1, 2, 2, 2, 1]


def test_white_notes_are_enumerated_without_accidentals():
    scale = Scale(notes='ABCDEFG')

    assert [scale.to_name(i) for i in range(8)] == [
        'C0',
        'D0',
        'E0',
        'F0',
        'G0',
        'A0',
        'B0',
        'C1',
    ]
    assert scale.to_number('D0') == 1
    assert scale.tuning_number(1) == Scale().to_number('D0')


def test_white_notes_reject_accidentals():
    scale = Scale(notes='ABCDEFG')

    try:
        scale.to_number('C♯0')
    except ValueError:
        pass
    else:
        raise AssertionError('C♯ should not be allowed')


def test_bad_notes_are_ignored() -> None:
    scale = Scale(notes='C frog D')

    assert scale._to_notes(scale.notes or '') == (['C', 'D'], ['frog'])
    assert [''.join(i) for i in scale.flats_sharps] == ['CD', 'CD']


def test_empty_or_bad_notes_use_scale_names() -> None:
    assert Scale(notes='')._to_notes('') == (list('CDEFGAB'), [])
    assert [''.join(i) for i in Scale(notes='frog').flats_sharps] == [
        'CDEFGAB',
        'CDEFGAB',
    ]


def test_scale():
    for i in range(-100, 100):
        name = tt.to_name(i)  # ty: ignore[missing-argument] !
        number = tt.to_number(name)
        assert number == i


def test_nearest_note():
    actual = [nearest_note(tt.tuning, i) for i in range(400, 500, 20)]
    expected = [(67, 68), (68, 69), 69, (69, 70), (70, 71)]
    assert actual == expected
