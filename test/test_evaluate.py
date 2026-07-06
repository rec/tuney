import random
from fractions import Fraction

from tuney.scale.evaluate import evaluate


def test_evaluate_fraction_expressions() -> None:
    assert evaluate('1 / 2 + 1 / 3') == Fraction(5, 6)
    assert evaluate('2 * (3 + 4)') == Fraction(14)
    assert evaluate('2**-1') == Fraction(1, 2)


def test_evaluate_float_expressions() -> None:
    assert evaluate('1.0 / 2 + 1 / 3') == 0.8333333333333333
    assert evaluate('2.0 * (3 + 4)') == 14.0
    assert evaluate('4.0**0.5') == 2.0
    assert evaluate('5.5 % 2') == 1.5
    assert evaluate('math.factorial(3) + 1') == 7.0


def test_evaluate_math_and_random_functions(monkeypatch) -> None:
    monkeypatch.setattr(random, 'random', lambda: 0.25)

    assert evaluate('math.sqrt(random.random()) ** 1.5') == 0.3535533905932738
