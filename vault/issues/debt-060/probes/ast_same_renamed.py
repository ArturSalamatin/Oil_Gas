"""Логика .py не изменилась с точностью до переименования (DEBT-060).

Запуск из корня репозитория (worktree):
    python ast_same_renamed.py <коммит базы> <файл> [<файл> ...]
Сравнивается AST без докстрингов модуля, классов и функций; в новой версии
имена из RENAME возвращаются к старым. Комментарии в AST не входят.
Выход: OK / DIFF по каждому файлу, код возврата — число DIFF.
"""
import ast
import subprocess
import sys

# Новое имя → старое (решение пользователя 2026-10-10, вариант B)
RENAME = {
    "_cell_centers_log_average": "_cell_centers_mass",
    "TestCellCenterLogAverage": "TestCenterMassVerification",
}


class _Back(ast.NodeTransformer):
    """Новые имена → старые: определения функций и классов, обращения по имени."""

    def visit_FunctionDef(self, node):
        node.name = RENAME.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        node.name = RENAME.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        node.id = RENAME.get(node.id, node.id)
        return node


def _dump(src: str, rename: bool) -> str:
    """ast.dump без докстрингов; при rename — с возвратом старых имён."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    if rename:
        tree = _Back().visit(tree)
    # Позиции (lineno, col_offset) ast.dump по умолчанию не печатает —
    # сдвиг строк от правки комментариев и докстрингов сравнению не мешает.
    return ast.dump(tree)


base, files = sys.argv[1], sys.argv[2:]
bad = 0
for rel in files:
    old = subprocess.run(["git", "show", f"{base}:{rel}"], capture_output=True,
                         check=True).stdout.decode("utf-8")
    with open(rel, encoding="utf-8") as fh:
        new = fh.read()
    same = _dump(old, rename=False) == _dump(new, rename=True)
    bad += not same
    print(("OK   " if same else "DIFF ") + rel)
print(f"файлов: {len(files)}, с изменённой логикой: {bad}")
sys.exit(bad)
