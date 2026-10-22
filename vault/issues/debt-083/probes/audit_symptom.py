"""DEBT-083, аудит 1: симптом на базе — gpn-solver run config.json --output <файл> в отдельном процессе.

Пакет и прототип — из дерева, где лежит сам скрипт (основной каталог или worktree):
подпроцесс получает PYTHONPATH и cwd этого дерева, путь пакета печатается (аудит 2:
без этого в worktree подпроцесс взял бы установленный пакет основного каталога).
Запуск: <PY> <дерево>\\vault\\issues\\debt-083\\probes\\audit_symptom.py. До правки — код 1,
после — код 2.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOLVER = ROOT / "numerical_solver"
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "GPN_EXAMPLES_EMF": "0",
       "PYTHONPATH": os.pathsep.join([str(SOLVER), str(PROTO)])}
pkg = subprocess.run([sys.executable, "-c", "import gpn_multiphase_solver as g; print(g.__file__)"],
                     cwd=SOLVER, env=ENV, capture_output=True, text=True).stdout.strip()
print("пакет:", pkg)
work = Path(__file__).resolve().parent / "_work_symptom"
if work.exists():
    shutil.rmtree(work)
(work / "case").mkdir(parents=True)
try:
    # Конфиг примера 03 на N = 20, одни сутки — как _small_case в tests/test_cli.py
    raw = json.loads((SOLVER / "examples" / "03_standing_corey" / "config.json").read_text(encoding="utf-8"))
    raw["grid"]["N"] = 20
    h0 = raw["time"]["history"][0]
    raw["time"]["history"] = [dict(h0, duration=86400.0, dt_out=43200.0)]
    raw["output"] = {"title": "симптом DEBT-083"}
    cfg = work / "case" / "config.json"
    cfg.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    f = work / "well_history.csv"
    f.write_text("1", encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "gpn_multiphase_solver", "run", str(cfg), "--output", str(f)],
                       cwd=SOLVER, env=ENV, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print("код возврата:", p.returncode)
    print("расчёт был:", "Сводка" in p.stdout or "Результаты" in p.stdout or "===" in p.stdout)
    print("последние строки stderr:")
    print("\n".join(p.stderr.strip().splitlines()[-3:]))
    print("файл цел:", f.read_text(encoding="utf-8") == "1")
finally:
    shutil.rmtree(work)
