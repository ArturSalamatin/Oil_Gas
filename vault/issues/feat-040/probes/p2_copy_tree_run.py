"""Проба FEAT-040, п. 2: копия дерева (два пакета + папка примера) считает книгу под python -S, пакеты – из копии.

Запуск из корня репозитория (или worktree – копируются пакеты своего дерева):
    <venv>\\Scripts\\python vault\\issues\\feat-040\\probes\\p2_copy_tree_run.py [путь к main.py]
Без аргумента берётся черновик main_draft.py рядом, с аргументом – указанный файл (при
реализации – numerical_solver\\examples\\23_source_tree_run\\main.py). Интерпретатор и
site-packages – того venv, которым запущена проба (в worktree своего .venv нет).
Копия – в probes\\out\\tree; каталог out\\ в git не входит, удалить после разбора. Итоги 2026-10-22 на 052d7d3: только расчёт и два
файла – код 0, 17.3 с; штатный набор – код 0, 32.4 с с векторными копиями (Inkscape 5.5 с),
23.6 с при GPN_EXAMPLES_EMF=0. __file__ обоих пакетов – из копии, 23 записи, на 30 сут
T_wf = 350.105 К, q_o = 3.077 м³ст/сут.
"""

import os
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
SITE = os.pathsep.join(dict.fromkeys(sysconfig.get_paths()[k] for k in ("purelib", "platlib")))
PY = sys.executable
NAME = "23_source_tree_run"
MAIN = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "main_draft.py"

sys.path.insert(0, str(SOLVER))
from gpn_multiphase_solver.io.workbook_template import write_template  # noqa: E402

out = HERE / "out"
shutil.rmtree(out, ignore_errors=True)
tree = out / "tree"
ignore = shutil.ignore_patterns("__pycache__")
shutil.copytree(SOLVER / "gpn_multiphase_solver", tree / "gpn_multiphase_solver", ignore=ignore)
shutil.copytree(PROTO / "radial_blackoil",
                tree / "HydroSolverPrototype" / "Prototype_1.0.3" / "radial_blackoil", ignore=ignore)
example = tree / "examples" / NAME
example.mkdir(parents=True)
shutil.copy(MAIN, example / "main.py")
write_template(example / f"{NAME}.xlsx")

env = dict(os.environ, PYTHONPATH=SITE, PYTHONIOENCODING="utf-8")
t0 = time.perf_counter()
r = subprocess.run([str(PY), "-S", str(example / "main.py")], cwd=out, env=env,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
elapsed = time.perf_counter() - t0
print("код:", r.returncode, f"| время процесса {elapsed:.1f} с")
print("--- stdout ---")
print(r.stdout)
print("--- stderr (последние 1500 знаков) ---")
print(r.stderr[-1500:])
print("--- файлы output ---")
for p in sorted((example / "output").rglob("*")):
    print(p.relative_to(example / "output"), p.stat().st_size if p.is_file() else "")
