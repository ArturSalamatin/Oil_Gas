"""Замер доли якобиана в расчёте примера: DEBT-033 (копия для DEBT-036; столбец «невязка» — цель DEBT-036).

Запуск — из каталога numerical_solver, код которого меряется (основного или worktree):
    .venv\\Scripts\\python d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-036\\probes\\time_jacobian.py [пример ...]

Методы прототипа оборачиваются таймерами в памяти; файлы примеров не пишутся.
"""
import sys
import time
from pathlib import Path

# Код — из каталога запуска: vault/issues/ в .gitignore, в worktree проб нет, их запускают
# по пути основного каталога, а мерить надо код worktree
SOLVER_ROOT = Path.cwd()
if not (SOLVER_ROOT / "gpn_multiphase_solver").is_dir():
    raise SystemExit("запускать из каталога numerical_solver (основного или worktree)")
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))

import radial_blackoil.blackoil as B  # noqa: E402
import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

print("код:", Path(B.__file__).parent, "|", Path(gpn_multiphase_solver.__file__).parent)

M = B.RadialBlackOilModel
acc = {}
in_jac = [False]  # невязка считается «внутри якобиана», пока идёт его сборка

orig_jac, orig_res, orig_lin, orig_csc = (
    M.finite_difference_jacobian, M.residual, M._linear_solve, B.csc_matrix)


def jac(self, *a, **k):
    in_jac[0] = True
    t = time.perf_counter()
    out = orig_jac(self, *a, **k)
    acc["jac"] += time.perf_counter() - t
    acc["njac"] += 1
    in_jac[0] = False
    return out


def res(self, *a, **k):
    t = time.perf_counter()
    out = orig_res(self, *a, **k)
    if in_jac[0]:
        acc["res_in_jac"] += time.perf_counter() - t
    return out


def lin(self, *a, **k):
    t = time.perf_counter()
    out = orig_lin(self, *a, **k)
    acc["lin"] += time.perf_counter() - t
    return out


def csc(*a, **k):
    # Перевод плотной матрицы 2N×2N в разреженную внутри _linear_solve
    t = time.perf_counter()
    out = orig_csc(*a, **k)
    acc["csc"] += time.perf_counter() - t
    return out


M.finite_difference_jacobian, M.residual, M._linear_solve, B.csc_matrix = jac, res, lin, csc

examples = sys.argv[1:] or ["20_rs300_cooling", "03_standing_corey", "04_table_table"]
for ex in examples:
    acc.update(jac=0.0, res_in_jac=0.0, lin=0.0, csc=0.0, njac=0)
    cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
    sim, s0 = SimulatorFactory.from_config(cfg)
    t = time.perf_counter()
    sim.run(s0)
    wall = time.perf_counter() - t
    overhead = acc["jac"] - acc["res_in_jac"]  # учёт раскраски без вычисления невязки
    print(f"{ex}: N={cfg.grid.N}, всего {wall:.2f} с; якобиан {acc['jac']:.2f} с "
          f"({100 * acc['jac'] / wall:.0f} %), из них невязка {acc['res_in_jac']:.2f} с, "
          f"учёт {overhead:.2f} с ({100 * overhead / wall:.0f} %); "
          f"перевод в разреженную {acc['csc']:.2f} с; линейное решение {acc['lin']:.2f} с; "
          f"якобианов {acc['njac']}")
