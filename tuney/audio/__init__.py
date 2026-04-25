import numpy as np

from ..types import Number

EPSILON = 1e-8


def apply_gain(data: np.ndarray, number: Number) -> None:
    if abs(number - 1.0) > EPSILON:
        data *= number
