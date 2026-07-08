import math
from fractions import Fraction
from typing import TypeAlias

type NoteNumber = int  # May be negative
if False:
    type Number = float | int | Fraction
else:
    Number: TypeAlias = float | int | Fraction


def cents(f: Number) -> float:
    return math.exp2(float(f) / 1200)


def uncents(c: Number) -> float:
    return math.log2(float(c)) * 1200
