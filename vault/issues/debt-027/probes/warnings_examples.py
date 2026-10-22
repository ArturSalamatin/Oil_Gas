"""DEBT-027: предупреждения журнала решателя на всех примерах — исходный замер и проверка реализации.

Каждый examples/*/config.json — через SimulatorFactory и Simulator.run (как CLI, без графиков).
Печать по примеру: записи журнала уровня WARNING с «вне таблиц» (DEBT-027) — полностью,
прочие WARNING — числом и первыми 60 символами (они не должны меняться).
Ожидание после DEBT-027: «вне таблиц» только у 04a — три категории (GAS_PVT pressure below
table и OIL_PVT saturated locus below table при t = 0.003472 сут, OIL_PVT saturated locus
above table при t = 0.08333 сут); у остальных 22 — нет. На базе 6d27358 — ни у одного.
Запуск из numerical_solver/ (worktree или основной каталог — печатается путь пакета):
    .venv\\Scripts\\python P [--emulate] [имя примера ...]
Без имён — все примеры, ~5 мин. --emulate — код плана подставлен в памяти (emulate_debt027.py).
"""
import logging
import sys
from pathlib import Path

import gpn_multiphase_solver
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

SOLVER = Path.cwd()
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
if "--emulate" in sys.argv:
    sys.argv.remove("--emulate")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import emulate_debt027
    emulate_debt027.install()
    print("эмуляция кода плана (emulate_debt027.install)", flush=True)

records = []


class Collect(logging.Handler):
    def emit(self, record):
        records.append(record)


logger = logging.getLogger("gpn_multiphase_solver")
logger.addHandler(Collect(level=logging.WARNING))

names = sys.argv[1:] or sorted(p.parent.name for p in (SOLVER / "examples").glob("*/config.json"))
total_range = 0
for name in names:
    records.clear()
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    sim, s0 = SimulatorFactory.from_config(cfg)
    # Консольный вывод INFO не нужен; WARNING собирает Collect (уровень логгера — WARNING)
    logger.setLevel(logging.WARNING)
    sim.run(s0)
    msgs = [r.getMessage() for r in records]
    rng = [m for m in msgs if "вне таблиц" in m]
    other = [m for m in msgs if "вне таблиц" not in m]
    total_range += len(rng)
    print(f"{name:30s} «вне таблиц»: {len(rng)}, прочих WARNING: {len(other)}", flush=True)
    for m in rng:
        print(f"    {m}")
    for m in other:
        print(f"    [прочее] {m[:60]}")
print(f"итог: записей «вне таблиц» {total_range} в {len(names)} примерах")
