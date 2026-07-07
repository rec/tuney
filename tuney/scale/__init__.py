import math
from fractions import Fraction

type NoteNumber = int  # May be negative


def cents(f: float | Fraction) -> float:
    return math.exp2(float(f) / 1200)


def uncents(c: float) -> float:
    return math.log2(c) * 1200
