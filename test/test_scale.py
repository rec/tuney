from test import twelve_tet as tt
from tuney.scale.nearest_note import nearest_note
from tuney.scale.scale import Scale


def test_flat_sharp():
    actual = [''.join(i) for i in Scale().flats_sharps]
    expected = ['CD♭DE♭EFG♭GA♭AB♭B', 'CC♯DD♯EFF♯GG♯AA♯B']

    assert actual == expected


def test_white_notes():
    actual = [''.join(i) for i in Scale(notes='ABCDEFG').flats_sharps]
    expected = ['CDEFGAB', 'CDEFGAB']

    assert actual == expected


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
