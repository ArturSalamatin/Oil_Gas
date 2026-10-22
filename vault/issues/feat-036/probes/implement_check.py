"""Реализация FEAT-036: файлы worktree равны коду плана — правки edits.py поверх базы и файлы plan_code.

Для каждого файла из аргументов: правки edits.py наложены на версию из точки
ветвления (git merge-base с базовой веткой) и сравнены с файлом worktree
побайтно; новые файлы — с копией в plan_code, блоки в конце — по вхождению.
Запуск из корня worktree:
    <PY> vault/issues/feat-036/probes/implement_check.py gpn_multiphase_solver/report/pipeline.py …
Пути — от numerical_solver/.
"""

import runpy
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parents[3]
SOLVER = W / "numerical_solver"
CODE = HERE / "plan_code"
EDITS = runpy.run_path(str(CODE / "edits.py"))["EDITS"]
# Новые файлы и блоки: путь от numerical_solver/ → (файл plan_code, "файл" | "блок")
COPIES = {
    "tests/test_workbook_run.py": ("test_workbook_run.py", "файл"),
    "tests/test_cli.py": ("test_cli_block.py", "блок"),
    "tests/test_examples.py": ("test_examples_block.py", "блок"),
    "examples/22_workbook_input/main.py": ("example_22/main.py", "файл"),
    "examples/22_workbook_input/README.md": ("example_22/README.md", "файл"),
}

base = subprocess.run(["git", "merge-base", "numerical_scheme/implementation", "HEAD"], cwd=W,
                      capture_output=True, text=True, check=True).stdout.strip()
for rel in sys.argv[1:]:
    text = (SOLVER / rel).read_text(encoding="utf-8")
    if rel in EDITS:
        expected = subprocess.run(["git", "show", f"{base}:numerical_solver/{rel}"], cwd=W,
                                  capture_output=True, check=True).stdout.decode("utf-8")
        for old, new in EDITS[rel]:
            assert expected.count(old) == 1, f"{rel}: «было» найдено {expected.count(old)} раз"
            expected = expected.replace(old, new)
        if rel in COPIES:                       # правки и блок в конце
            expected += (CODE / COPIES[rel][0]).read_text(encoding="utf-8")
    else:
        expected = (CODE / COPIES[rel][0]).read_text(encoding="utf-8")
    print(f"{rel}: {'равен коду плана' if text == expected else 'ОТЛИЧАЕТСЯ от кода плана'}")
