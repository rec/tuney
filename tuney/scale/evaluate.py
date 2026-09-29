import ast
import math
import operator
import random
from collections.abc import Callable, Iterable
from fractions import Fraction
from functools import cached_property, singledispatchmethod

from ufor.number import PitchNumber, cents_to_ratio

MODULES = {'math': math, 'random': random}
FUNCTIONS = {'cents': cents_to_ratio}
MAX_EXPRESSION_LENGTH = 1024
MAX_EXPRESSION_NODES = 128
MAX_ARGUMENT = 10_000
MAX_FACTORIAL_ARGUMENT = 1_000
MAX_POWER_EXPONENT = 256
MAX_RESULT_BITS = 4_096


def evaluate(expression: str) -> PitchNumber:
    return _Evaluate(expression).evaluate()


def evaluate_all(expressions: Iterable[str]) -> list[PitchNumber]:
    values, bad = [], []
    for s in expressions:
        try:
            values.append(evaluate(s))
        except Exception:
            bad.append(s)
    if bad:
        msg = ', '.join(f'"{e}"' for e in bad)
        raise ValueError(f'Bad expressions {msg}')
    return values


class _Evaluate:
    def __init__(self, expression: str) -> None:
        self.expression = expression

    def evaluate(self) -> PitchNumber:
        return self._eval(self.root)

    @cached_property
    def root(self) -> ast.AST:
        if len(self.expression) > MAX_EXPRESSION_LENGTH:
            raise ValueError('Expression is too long')
        root = ast.parse(
            self.expression.partition('#')[0].replace('^', '**'), mode='eval'
        )
        if sum(1 for _ in ast.walk(root)) > MAX_EXPRESSION_NODES:
            raise ValueError('Expression is too complex')
        return root

    @singledispatchmethod
    def _eval(self, node: ast.AST) -> PitchNumber:
        raise ValueError(f'Unsupported expression {ast.unparse(node)}')

    @_eval.register
    def _(self, node: ast.Expression) -> PitchNumber:
        return self._eval(node.body)

    @_eval.register
    def _(self, node: ast.Constant) -> PitchNumber:
        if type(node.value) is int:
            return self.number(node.value)
        if type(node.value) is float:
            return self.number(node.value)
        raise ValueError(f'Unsupported expression {ast.unparse(node)}')

    @_eval.register
    def _(self, node: ast.BinOp) -> PitchNumber:
        if (operation := BINARY_OPERATORS.get(type(node.op))) is None:
            raise ValueError(
                f'Unsupported binary operator {node.op.__class__.__name__}'
            )
        left, right = self._eval(node.left), self._eval(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_POWER_EXPONENT:
                raise ValueError('Exponent is too large')
            if (
                isinstance(left, Fraction)
                and isinstance(right, Fraction)
                and right.denominator == 1
            ):
                bits = max(left.numerator.bit_length(), left.denominator.bit_length())
                if bits * abs(right.numerator) > MAX_RESULT_BITS:
                    raise ValueError('Power result is too large')
        return self.checked(operation(left, right))

    @_eval.register
    def _(self, node: ast.UnaryOp) -> PitchNumber:
        value = self._eval(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return self.checked(-value)
        raise ValueError(f'Unsupported unary operator {node.op.__class__.__name__}')

    @_eval.register
    def _(self, node: ast.Call) -> PitchNumber:
        if node.keywords:
            raise ValueError('Keyword arguments are not supported')

        if isinstance((f := node.func), ast.Name) and f.id in FUNCTIONS:
            args = (self._eval(a) for a in node.args)
            result = FUNCTIONS[f.id](*args)
            if isinstance(result, (float, Fraction)):
                return self.checked(result)
            raise TypeError(f'Function returned unsupported value {result!r}')

        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)):
            raise ValueError('Only math and random attributes can be used')
        if f.attr.startswith('_'):
            raise ValueError(f'Private attributes {f.attr!r} are not allowed')
        if f.value.id not in MODULES:
            raise NameError(f'Unknown module {f.value.id!r}')
        if f.value.id == 'random' and f.attr not in RANDOM_FUNCTIONS:
            raise ValueError(f'Unsupported random function {f.attr!r}')

        func = getattr(MODULES[f.value.id], f.attr)
        if not callable(func):
            raise TypeError(f'{ast.unparse(f)} is not callable')

        def convert(node: ast.AST) -> PitchNumber:
            v = float(self._eval(node))
            if not math.isfinite(v) or abs(v) > MAX_ARGUMENT:
                raise ValueError('Function argument is too large')
            return int(v) if v.is_integer() else v

        args = [convert(a) for a in node.args]
        if (
            f.attr in {'factorial', 'comb', 'perm'}
            and args
            and args[0] > MAX_FACTORIAL_ARGUMENT
        ):
            raise ValueError('Factorial argument is too large')
        if f.attr == 'pow' and len(args) > 1 and abs(args[1]) > MAX_POWER_EXPONENT:
            raise ValueError('Exponent is too large')
        result = func(*args)
        if isinstance(result, PitchNumber):
            return self.number(result)
        raise TypeError(f'Function returned unsupported value {result!r}')

    @_eval.register
    def _(self, node: ast.Attribute) -> PitchNumber:
        if not isinstance(node.value, ast.Name):
            raise ValueError('Only math and random attributes can be used')
        if node.attr.startswith('_'):
            raise ValueError(f'Private attribute {node.attr!r} is not allowed')
        if node.value.id not in MODULES:
            raise NameError(f'Unknown name {node.value.id!r}')
        value = getattr(MODULES[node.value.id], node.attr)
        if isinstance(value, PitchNumber):
            return self.number(value)
        raise TypeError(f'Attribute {ast.unparse(node)} is not numeric')

    def number(self, v: PitchNumber) -> PitchNumber:
        result = Fraction(str(v)) if isinstance(v, float) else Fraction(v)
        return self.checked(result)

    def checked(self, v: object) -> PitchNumber:
        if isinstance(v, complex):
            raise ValueError('Expression result must be real')
        if isinstance(v, float):
            if not math.isfinite(v):
                raise ValueError('Expression result must be finite')
            return v
        if not isinstance(v, (int, Fraction)):
            raise TypeError(f'Expression returned unsupported value {v!r}')
        result = Fraction(v)
        if (
            result.numerator.bit_length() > MAX_RESULT_BITS
            or result.denominator.bit_length() > MAX_RESULT_BITS
        ):
            raise ValueError('Expression result is too large')
        return v


BINARY_OPERATORS: dict[
    type[ast.operator], Callable[[PitchNumber, PitchNumber], PitchNumber]
] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

RANDOM_FUNCTIONS = {
    'random',
    'uniform',
    'triangular',
    'randint',
    'randrange',
    'gauss',
    'normalvariate',
    'expovariate',
    'betavariate',
    'gammavariate',
    'lognormvariate',
    'vonmisesvariate',
    'paretovariate',
    'weibullvariate',
    'getrandbits',
}
