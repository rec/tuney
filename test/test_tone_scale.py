from itertools import product

import pytest

from test import twelve_tet as tt
from tuney.scale.scale import Scale

NAMES = sorted(set(tt.NUMBER_TO_NAME[tt.FLAT] + tt.NUMBER_TO_NAME[tt.SHARP]))
NAME_OCTAVE = list(product(NAMES, range(10)))[::7]
TS = Scale(offset=12)
NUMBERS = list(product(range(-7, 7), (False, True)))[::5]


@pytest.mark.parametrize('name, octave', NAME_OCTAVE)
def test_all_scale_names(name, octave):
    name += str(octave)
    number = TS.to_number(name)
    new_name = TS.to_name(number, use_sharp=tt.SHARP in name)
    assert name == new_name


@pytest.mark.parametrize('number, use_sharp', NUMBERS)
def test_all_scale_numbers(number, use_sharp):
    name = TS.to_name(number, use_sharp)
    new_number = TS.to_number(name)
    assert number == new_number
    assert name == tt.to_name(number, use_sharp)
