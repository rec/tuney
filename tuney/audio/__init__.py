import numpy as np

EPSILON = 1e-8


def apply_gain(a: np.ndarray, number: float) -> None:
    if abs(number - 1.0) > EPSILON:
        a *= number
