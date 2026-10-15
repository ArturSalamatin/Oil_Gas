"""AST изменённых .py без докстрингов совпадает с коммитом базы — правки только в тексте.

Запуск из корня worktree:
    <PY> vault\\issues\\debt-070\\probes\\ast_same.py <коммит базы> <файл> [<файл> ...]
"""

import ast
import subprocess
import sys


def strip_docstrings(src):
    """ast.dump без докстрингов модуля, классов и функций."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant) and isinstance(
                    body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def main():
    base, files = sys.argv[1], sys.argv[2:]
    for f in files:
        old = subprocess.check_output(["git", "show", f"{base}:{f}"]).decode("utf-8")
        with open(f, encoding="utf-8") as fh:
            new = fh.read()
        same = strip_docstrings(old) == strip_docstrings(new)
        print(f"{f}: ast без докстрингов {'совпадает' if same else 'ОТЛИЧАЕТСЯ'}")


if __name__ == "__main__":
    main()
