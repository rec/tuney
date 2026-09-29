import math
import random
from fractions import Fraction

import pytest

from tuney.scale.evaluate import evaluate


def test_evaluate_fraction_expressions() -> None:
    assert evaluate('1 / 2 + 1 / 3') == Fraction(5, 6)
    assert evaluate('2 * (3 + 4)') == Fraction(14)
    assert evaluate('2**-1') == Fraction(1, 2)


def test_evaluate_float_expressions() -> None:
    assert evaluate('1.0 / 2 + 1 / 3') == Fraction(5, 6)
    assert evaluate('2.0 * (3 + 4)') == Fraction(14)
    assert evaluate('4.0**0.5') == 2.0
    assert evaluate('5.5 % 2') == Fraction(3, 2)
    assert evaluate('math.factorial(3) + 1') == Fraction(7)
    assert evaluate('cents(1 / 2)') == math.exp2(0.5 / 1200)


def test_evaluate_math_and_random_functions(monkeypatch) -> None:
    monkeypatch.setattr(random, 'random', lambda: 0.25)

    assert evaluate('math.sqrt(random.random()) ** 1.5') == 0.3535533905932738


@pytest.mark.parametrize(
    ('expression', 'message'),
    [
        ('2**1000000000', 'Exponent is too large'),
        ('(2**256)**256', 'Power result is too large'),
        ('math.factorial(1000000000)', 'Function argument is too large'),
        ('random.getrandbits(1000000000)', 'Function argument is too large'),
        ('1+' * 600 + '1', 'Expression is too long'),
        ('1+' * 70 + '1', 'Expression is too complex'),
    ],
)
def test_expensive_expressions_are_rejected(expression: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        evaluate(expression)


def test_stateful_random_calls_are_rejected_before_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        random, 'seed', lambda *_: pytest.fail('random.seed was called')
    )

    with pytest.raises(ValueError, match='Unsupported random function'):
        evaluate('random.seed(1)')
