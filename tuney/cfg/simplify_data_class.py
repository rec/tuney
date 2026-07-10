from __future__ import annotations

import ast
from collections.abc import Container, Iterable
from pathlib import Path


def simplify_data_class(
    paths: Iterable[Path | str], remove: Container[str] = ()
) -> str:
    classes: list[ast.stmt] = []
    for path in paths:
        text = Path(path).read_text()
        tree = ast.parse(text)
        base_model_classes = _base_model_classes(tree)
        comments = _member_comments(text.splitlines())
        for s in tree.body:
            if isinstance(s, ast.ClassDef) and s.name in base_model_classes:
                classes.append(_simplify_class(s, comments, remove))

    simplified = ast.Module(body=classes, type_ignores=[])
    ast.fix_missing_locations(simplified)
    text = _restore_comments(ast.unparse(simplified))
    return _space_members(_space_classes(text)) + '\n'


def _space_classes(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith('class ') and lines and not lines[-1]:
            lines.append('')
        lines.append(line)
    return '\n'.join(lines)


def _space_members(text: str) -> str:
    lines: list[str] = []
    previous_member = False
    pending_comment = False
    for line in text.splitlines():
        if pending_comment and not line:
            continue
        if _is_member_start(line) and previous_member:
            lines.append('')
        lines.append(line)
        pending_comment = line.strip().startswith('#')
        previous_member = _is_member_line(line)
    return '\n'.join(lines)


def _is_member_start(line: str) -> bool:
    stripped = line.strip()
    return line.startswith('    ') and (
        stripped.startswith('#') or _is_member_line(line)
    )


def _is_member_line(line: str) -> bool:
    stripped = line.strip()
    return line.startswith('    ') and ':' in stripped and not stripped.startswith('#')


def _restore_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if (comment := _comment(line)) is not None:
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(indent + comment)
        else:
            lines.append(line)
    return '\n'.join(lines)


def _comment(line: str) -> str | None:
    try:
        value = ast.literal_eval(line.strip())
    except (SyntaxError, ValueError):
        return None
    if isinstance(value, str) and value.startswith(_COMMENT_PREFIX):
        return value[len(_COMMENT_PREFIX) :]
    return None


def _member_comments(lines: list[str]) -> dict[int, list[str]]:
    comments: dict[int, list[str]] = {}
    for n, line in enumerate(lines, start=1):
        if not line[:1].isspace() or ':' not in line:
            continue
        member_comments = _preceding_comments(lines, n)
        if member_comments:
            comments[n] = member_comments
    return comments


def _preceding_comments(lines: list[str], line_number: int) -> list[str]:
    comments: list[str] = []
    index = line_number - 2
    while index >= 0 and lines[index].lstrip().startswith('#'):
        comments.append(lines[index].strip())
        index -= 1
    return list(reversed(comments))


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
    models = {*base_model_classes, 'BaseModel'}
    return any(_base_name(b) in models for b in node.bases)


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return None


def _simplify_class(
    node: ast.ClassDef, comments: dict[int, list[str]], remove: Container[str]
) -> ast.ClassDef:
    node.bases = []
    node.keywords = []
    body: list[ast.stmt] = []
    for s in node.body:
        if _remove_statement(s, remove):
            continue
        if isinstance(s, ast.AnnAssign):
            body.extend(_comment_nodes(comments.get(s.lineno, [])))
        body.append(_simplify_field(s))
    node.body = body
    if not node.body:
        node.body = [ast.Pass()]
    return node


def _comment_nodes(comments: list[str]) -> list[ast.Expr]:
    return [ast.Expr(value=ast.Constant(value=_COMMENT_PREFIX + c)) for c in comments]


def _remove_statement(statement: ast.stmt, remove: Container[str]) -> bool:
    if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
        return True
    return isinstance(statement, ast.AnnAssign) and (
        _remove_member(statement.target, remove) or _has_hidden(statement.annotation)
    )


def _remove_member(node: ast.expr, remove: Container[str]) -> bool:
    return isinstance(node, ast.Name) and (node.id.startswith('_') or node.id in remove)


def _simplify_field(statement: ast.stmt) -> ast.stmt:
    if not isinstance(statement, ast.AnnAssign):
        return statement
    annotation = _simplify_annotation(statement.annotation)
    return ast.AnnAssign(
        target=statement.target,
        annotation=annotation,
        value=_simplify_value(annotation, statement.value),
        simple=statement.simple,
    )


def _simplify_value(annotation: ast.expr, node: ast.expr | None) -> ast.expr | None:
    if node is None:
        return None
    if isinstance(node, ast.Call) and _base_name(node.func) == 'Field':
        return node.args[0] if node.args else None
    if _empty_constructor(node):
        return None
    return node


def _empty_constructor(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and not node.args and not node.keywords


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
_COMMENT_PREFIX = '__COMMENT__'
