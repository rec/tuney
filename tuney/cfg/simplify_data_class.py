from __future__ import annotations

import ast
from pathlib import Path


def simplify_data_class(path: Path | str) -> str:
    tree = ast.parse(Path(path).read_text())
    base_model_classes = _base_model_classes(tree)
    simplified = _SimplifyDataClasses(base_model_classes).visit(tree)
    assert isinstance(simplified, ast.Module)
    ast.fix_missing_locations(simplified)
    return ast.unparse(simplified) + '\n'


def _base_model_classes(tree: ast.Module) -> set[str]:
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    base_model_classes: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name not in base_model_classes and _extends_base_model(
                node, base_model_classes
            ):
                base_model_classes.add(node.name)
                changed = True
    return base_model_classes


def _extends_base_model(node: ast.ClassDef, base_model_classes: set[str]) -> bool:
    return any(
        _base_name(base) in {*base_model_classes, 'BaseModel'} for base in node.bases
    )


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return None


class _SimplifyDataClasses(ast.NodeTransformer):
    def __init__(self, base_model_classes: set[str]) -> None:
        self.base_model_classes = base_model_classes

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        if node.name not in self.base_model_classes:
            return node
        node.body = [
            statement for statement in node.body if not _remove_statement(statement)
        ]
        node.body = [_simplify_field(statement) for statement in node.body]
        if not node.body:
            node.body = [ast.Pass()]
        return node


def _remove_statement(statement: ast.stmt) -> bool:
    if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
        return True
    return isinstance(statement, ast.AnnAssign) and _has_hidden(statement.annotation)


def _simplify_field(statement: ast.stmt) -> ast.stmt:
    if not isinstance(statement, ast.AnnAssign):
        return statement
    annotation = _simplify_annotation(statement.annotation)
    return ast.AnnAssign(
        target=statement.target,
        annotation=annotation,
        value=(
            _constructor_value(annotation)
            if _replace_value(statement.value)
            else statement.value
        ),
        simple=statement.simple,
    )


def _replace_value(node: ast.expr | None) -> bool:
    return node is None or (
        isinstance(node, ast.Call) and _base_name(node.func) == 'Field'
    )


def _constructor_value(annotation: ast.expr) -> ast.expr:
    if isinstance(annotation, ast.Name | ast.Attribute):
        return ast.Call(func=annotation, args=[], keywords=[])
    return ast.Constant(value=None)


def _simplify_annotation(node: ast.expr) -> ast.expr:
    if (
        not isinstance(node, ast.Subscript)
        or (base_name := _base_name(node.value)) not in _ANNOTATION_WRAPPERS
    ):
        return node
    if base_name == 'Annotated' and isinstance(node.slice, ast.Tuple):
        return _simplify_annotation(node.slice.elts[0])
    return _simplify_annotation(node.slice)


def _has_hidden(node: ast.AST) -> bool:
    return any(_hidden_node(child) for child in ast.walk(node))


def _hidden_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == 'Hidden'
    if isinstance(node, ast.Attribute):
        return node.attr == 'Hidden'
    return False


_ANNOTATION_WRAPPERS = {'Annotated', 'SkipJsonSchema', 'Suppress'}
