"""Логика .py не изменилась: AST без докстрингов совпадает с базой (DEBT-010).

Запуск из корня worktree:  python ast_same.py <коммит базы>
Сравниваются изменённые (M) файлы *.py; новые (A) пропускаются.
Комментарии в AST не входят, докстринги модуля, классов и функций удаляются.
"""
import ast
import subprocess
import sys


def _strip_docstrings(src: str) -> str:
    """ast.dump без докстрингов модуля, классов и функций."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    # Позиции (lineno, col_offset) ast.dump по умолчанию не печатает —
    # сдвиг строк от переноса докстринга сравнению не мешает.
    return ast.dump(tree)


def _git(*args) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


base = sys.argv[1]
files = _git("diff", "--name-only", "--diff-filter=M", base,
             "--", "*.py").decode().split()
bad = 0
for rel in files:
    old = _git("show", f"{base}:{rel}").decode("utf-8")
    with open(rel, encoding="utf-8") as fh:
        new = fh.read()
    same = _strip_docstrings(old) == _strip_docstrings(new)
    bad += not same
    print(("OK   " if same else "DIFF ") + rel)
print(f"файлов: {len(files)}, с изменённой логикой: {bad}")
sys.exit(1 if bad else 0)
