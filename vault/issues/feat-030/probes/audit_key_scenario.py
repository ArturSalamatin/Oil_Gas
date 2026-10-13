"""Аудит FEAT-030: ключевой сценарий теста команды (test_cli.py::test_run_from_foreign_directory).

План: конфиг примера 03 с grid.N = 20 и одним интервалом 1 сут (dt_out 12 ч),
output.title = "тест команды"; запуск из постороннего каталога; ожидается код 0,
12 файлов в output и ~8 с. Команды ещё нет — эмуляция тем, что она будет звать:
run_example (с шага 5 — обёртка над run_case) в отдельном процессе, каталог
запуска — посторонний, PYTHONPATH — пакет и прототип этого дерева, examples/.
steady_state=False — как умолчание команды (решение 2026-10-13).

Заодно: защита входных файлов — есть ли у 03 CSV (нет: Standing + Corey), и
что печать «Конфиг: …» содержит абсолютный путь, если его передать.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-030\\probes\\audit_key_scenario.py
Рабочий каталог — vault/issues/feat-030/probes/out/key_scenario (не коммитится).
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SOLVER = Path.cwd().resolve()
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
WORK = Path(__file__).resolve().parent / "out" / "key_scenario"
print(f"дерево: {SOLVER}")

if WORK.exists():
    shutil.rmtree(WORK)
case = WORK / "case"
case.mkdir(parents=True)
raw = json.loads((SOLVER / "examples" / "03_standing_corey" / "config.json")
                 .read_text(encoding="utf-8"))
raw["grid"]["N"] = 20
h0 = raw["time"]["history"][0]
raw["time"]["history"] = [dict(h0, duration=86400.0, dt_out=43200.0)]
raw["output"] = {"log_level": "INFO"}
(case / "config.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2),
                                  encoding="utf-8")

code = (
    "import sys; from pathlib import Path; "
    "from example_runner import run_example; "
    "run_example(Path(sys.argv[1]).resolve(), None or Path(sys.argv[1]).resolve().parent / 'output', "
    "'тест команды', steady_state=False)"
)
env = dict(os.environ, PYTHONIOENCODING="utf-8", GPN_EXAMPLES_EMF="0",
           PYTHONPATH=os.pathsep.join([str(SOLVER), str(PROTO), str(SOLVER / "examples")]))
t0 = time.perf_counter()
p = subprocess.run([sys.executable, "-c", code, "case/config.json"], cwd=WORK, env=env,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
dt = time.perf_counter() - t0
files = sorted(f.name for f in (case / "output").iterdir()) if (case / "output").is_dir() else []
print(f"код {p.returncode}, {dt:.1f} с, файлов {len(files)}")
print("  " + ", ".join(files))
lines = p.stdout.splitlines()
print("  stdout[0:2]:", lines[:2])
print("  'Шагов сохранено' в выводе:", any(s.startswith("Шагов сохранено") for s in lines))
if p.returncode:
    print(p.stderr[-1500:])
