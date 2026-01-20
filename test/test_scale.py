from tuney.scale.twelve_tet import TWELVE_TET as tt
from tuney.scale.nearest_note import nearest_note

assert tt


def test_scale():
    for i in range(-100, 100):
        name = tt.number_to_name(i)  # ty: ignore[missing-argument] !
        number = tt.name_to_number(name)
        assert number == i


def test_nearest_note():
    actual = [nearest_note(tt.scale, i) for i in range(400, 500, 20)]
    expected = [(67, 68), (68, 69), 69, (69, 70), (70, 71)]
    assert actual == expected
