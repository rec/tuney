import ast
import math
import operator as op
import random
from collections.abc import Callable, Iterable
from fractions import Fraction
from functools import cached_property, singledispatchmethod

from . import cents

MODULES = {'math': math, 'random': random}
FUNCTIONS = {'cents': cents}


def evaluate(expression: str) -> float | Fraction:
    return _Evaluate(expression).evaluate()


def evaluate_all(expressions: Iterable[str]) -> list[float | Fraction]:
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

    def evaluate(self) -> float | Fraction:
        return self._eval(self.root)

    @cached_property
    def root(self) -> ast.AST:
        return ast.parse(self.expression.partition('#')[0], mode='eval')

    @singledispatchmethod
    def _eval(self, node: ast.AST) -> float | Fraction:
        raise ValueError(f'Unsupported expression {ast.unparse(node)}')

    @_eval.register
    def _(self, node: ast.Expression) -> float | Fraction:
        return self._eval(node.body)

    @_eval.register
    def _(self, node: ast.Constant) -> float | Fraction:
        if type(node.value) is int:
            return self.number(node.value)
        if type(node.value) is float:
            return self.number(node.value)
        raise ValueError(f'Unsupported expression {ast.unparse(node)}')

    @_eval.register
    def _(self, node: ast.BinOp) -> float | Fraction:
        if (operation := BINARY_OPERATORS.get(type(node.op))) is None:
            raise ValueError(
                f'Unsupported binary operator {node.op.__class__.__name__}'
            )
        return operation(self._eval(node.left), self._eval(node.right))

    @_eval.register
    def _(self, node: ast.UnaryOp) -> float | Fraction:
        value = self._eval(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError(f'Unsupported unary operator {node.op.__class__.__name__}')

    @_eval.register
    def _(self, node: ast.Call) -> float | Fraction:
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

        def convert(node: ast.AST) -> float | int | Fraction:
            v = float(self._eval(node))
            return int(v) if v.is_integer() else v

        result = func(*(convert(a) for a in node.args))
        if isinstance(result, int | float | Fraction):
            return self.number(result)
        raise TypeError(f'Function returned unsupported value {result!r}')

    @_eval.register
    def _(self, node: ast.Attribute) -> float | Fraction:
        if not isinstance(node.value, ast.Name):
            raise ValueError('Only math and random attributes can be used')
        if node.attr.startswith('_'):
            raise ValueError(f'Private attribute {node.attr!r} is not allowed')
        if node.value.id not in MODULES:
            raise NameError(f'Unknown name {node.value.id!r}')
        value = getattr(MODULES[node.value.id], node.attr)
        if isinstance(value, int | float | Fraction):
            return self.number(value)
        raise TypeError(f'Attribute {ast.unparse(node)} is not numeric')

    def number(self, v: int | float | Fraction) -> float | Fraction:
        return Fraction(str(v)) if isinstance(v, float) else Fraction(v)


BINARY_OPERATORS: dict[
    type[ast.operator], Callable[[float | Fraction, float | Fraction], float | Fraction]
] = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
}
