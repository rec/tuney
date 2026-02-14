from ..types import Data, Number

EPSILON = 1e-8


def apply_gain(data: Data, number: Number) -> None:
    if abs(number - 1.0) > EPSILON:
        data *= number
