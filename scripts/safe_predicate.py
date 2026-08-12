"""Side-effect-free predicate evaluator for project governance checks."""
from __future__ import annotations

import ast
from pathlib import Path


class UnsafePredicate(ValueError):
    pass


def _project_path(project: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise UnsafePredicate("path must be a non-empty string")
    path = (project / raw).resolve()
    try:
        path.relative_to(project)
    except ValueError as exc:
        raise UnsafePredicate("path escapes project directory") from exc
    return path


def _functions(project: Path):
    def path(raw):
        return _project_path(project, raw)

    def read(raw):
        return path(raw).read_text(encoding="utf-8", errors="replace")

    return {
        "is_file": lambda raw: path(raw).is_file(),
        "is_dir": lambda raw: path(raw).is_dir(),
        "nonempty_file": lambda raw: path(raw).is_file() and path(raw).stat().st_size > 0,
        "contains": lambda raw, text: str(text) in read(raw),
        "has_line": lambda raw, prefix, excluded="": any(
            line.startswith(str(prefix)) and (not excluded or str(excluded) not in line)
            for line in read(raw).splitlines()
        ),
        "all_files": lambda values: all(path(raw).is_file() for raw in values),
        "all_dirs": lambda values: all(path(raw).is_dir() for raw in values),
        "python_syntax": lambda raw: _python_syntax(path(raw)),
    }


def _python_syntax(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        return True
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False


def evaluate_predicate(expression: str, project_dir: Path | str) -> bool:
    project = Path(project_dir).resolve()
    try:
        tree = ast.parse(str(expression), mode="eval")
    except SyntaxError as exc:
        raise UnsafePredicate(f"invalid syntax: {exc.msg}") from exc
    functions = _functions(project)

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool, type(None))):
                return node.value
            raise UnsafePredicate("unsupported constant")
        if isinstance(node, (ast.List, ast.Tuple)):
            return [visit(item) for item in node.elts]
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [bool(visit(item)) for item in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not bool(visit(node.operand))
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            for operator, comparator in zip(node.ops, node.comparators):
                right = visit(comparator)
                if isinstance(operator, ast.Eq):
                    passed = left == right
                elif isinstance(operator, ast.NotEq):
                    passed = left != right
                elif isinstance(operator, ast.Lt):
                    passed = left < right
                elif isinstance(operator, ast.LtE):
                    passed = left <= right
                elif isinstance(operator, ast.Gt):
                    passed = left > right
                elif isinstance(operator, ast.GtE):
                    passed = left >= right
                elif isinstance(operator, ast.In):
                    passed = left in right
                elif isinstance(operator, ast.NotIn):
                    passed = left not in right
                elif isinstance(operator, ast.Is):
                    passed = left is right
                elif isinstance(operator, ast.IsNot):
                    passed = left is not right
                else:
                    raise UnsafePredicate("unsupported comparison")
                if not passed:
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = functions.get(node.func.id)
            if function is None or node.keywords:
                raise UnsafePredicate(f"function is not allowed: {node.func.id}")
            return function(*[visit(arg) for arg in node.args])
        raise UnsafePredicate(f"node is not allowed: {type(node).__name__}")

    return bool(visit(tree))


def run_predicate(expression: str, project_dir: Path | str) -> tuple[bool, str]:
    try:
        passed = evaluate_predicate(expression, project_dir)
        return passed, "通过" if passed else "失败"
    except (UnsafePredicate, OSError, TypeError, ValueError) as exc:
        return False, f"UNSAFE_PREDICATE: {exc}"
