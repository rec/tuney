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
        return ast.parse(
            self.expression.partition('#')[0].replace('^', '**'), mode='eval'
        )

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
        return operation(self._eval(node.left), self._eval(node.right))

    @_eval.register
    def _(self, node: ast.UnaryOp) -> PitchNumber:
        value = self._eval(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError(f'Unsupported unary operator {node.op.__class__.__name__}')

    @_eval.register
    def _(self, node: ast.Call) -> PitchNumber:
        if node.keywords:
            raise ValueError('Keyword arguments are not supported')

        if isinstance((f := node.func), ast.Name) and f.id in FUNCTIONS:
            args = (self._eval(a) for a in node.args)
            result = FUNCTIONS[f.id](*args)
            if isinstance(result, (float, Fraction)):
                return result
            raise TypeError(f'Function returned unsupported value {result!r}')

        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)):
            raise ValueError('Only math and random attributes can be used')
        if f.attr.startswith('_'):
            raise ValueError(f'Private attributes {f.attr!r} are not allowed')
        if f.value.id not in MODULES:
            raise NameError(f'Unknown module {f.value.id!r}')

        func = getattr(MODULES[f.value.id], f.attr)
        if not callable(func):
            raise TypeError(f'{ast.unparse(f)} is not callable')

        def convert(node: ast.AST) -> PitchNumber:
            v = float(self._eval(node))
            return int(v) if v.is_integer() else v

        result = func(*(convert(a) for a in node.args))
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
        return Fraction(str(v)) if isinstance(v, float) else Fraction(v)


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
