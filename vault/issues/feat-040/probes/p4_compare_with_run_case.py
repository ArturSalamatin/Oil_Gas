"""Проба FEAT-040, п. 4: штатный набор main.py примера 23 (вывод пробы p2) против run_case на той же книге – состав и байты файлов.

Запуск из корня репозитория после p2 с GPN_EXAMPLES_EMF=0 (как в тестах):
    $env:GPN_EXAMPLES_EMF = "0"
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\feat-040\\probes\\p2_copy_tree_run.py
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\feat-040\\probes\\p4_compare_with_run_case.py
run_case считает копию книги в probes\\out\\run_case\\ (каталог out\\ удалить после разбора).
"""

import contextlib
import io
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
NAME = "23_source_tree_run"
os.environ.setdefault("GPN_EXAMPLES_EMF", "0")
sys.path.insert(0, str(SOLVER))

from gpn_multiphase_solver.cli import configure_batch_run  # noqa: E402
from gpn_multiphase_solver.report.pipeline import run_case  # noqa: E402

configure_batch_run()
main_out = HERE / "out" / "tree" / "examples" / NAME / "output"
case = HERE / "out" / "run_case"
shutil.rmtree(case, ignore_errors=True)
case.mkdir(parents=True)
book = case / f"{NAME}.xlsx"
shutil.copy(main_out.parent / f"{NAME}.xlsx", book)
with contextlib.redirect_stdout(io.StringIO()):
    run_case(book)
ref_out = case / "output"


def files(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


a, b = files(main_out), files(ref_out)
print("только у main.py:", sorted(set(a) - set(b)))
print("только у run_case:", sorted(set(b) - set(a)))
for name in sorted(set(a) & set(b)):
    same = a[name].read_bytes() == b[name].read_bytes()
    print(f"{'=' if same else '≠'} {name}")
