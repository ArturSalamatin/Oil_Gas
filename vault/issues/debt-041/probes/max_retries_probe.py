"""DEBT-041: минимально достаточный numerics.max_retries примера 03 — по всем вызовам гидро за прогон.

Адаптер дробит шаг равномерно: попытка a даёт 2**a подшагов (prototype_adapter.py, A-retry), первая
сошедшаяся попытка от лимита не зависит. Симулятор после дробления проходит интервал заново подшагами,
и каждый такой вызов адаптера дробится с тем же лимитом (simulator.py, _advance). Поэтому при лимите m
прогон идёт побитно как при умолчании 9, пока какому-то вызову не понадобится попытка a > m, — там
RuntimeError. Минимально достаточный лимит: k = max по вызовам log2(n_substeps) одного прогона при
умолчании. Контроль — прогон с k − 1: обязан упасть на вызове, где достигнут максимум.

Точки — таблица README 03 (N = 150, p_wf на всех интервалах истории) и строка «при 8 МПа сгущение
сетки дробления не требует» (N = 50, 75, 100, 140, 200).

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\max_retries_probe.py
"""
import logging
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
logging.disable(logging.INFO)

import gpn_multiphase_solver  # noqa: E402
import radial_blackoil  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CONFIG = SOLVER_ROOT / "examples" / "03_standing_corey" / "config.json"
DAY = 86400.0
CASES = [(150, p) for p in (8.0, 7.5, 7.0, 6.0, 5.0, 4.0, 2.0, 0.5)] + \
        [(N, 8.0) for N in (50, 75, 100, 140, 200)]


def run(N, pwf_MPa, max_retries=None):
    """Полный прогон истории; возвращает журнал вызовов гидро, конечное p и исключение (или None)."""
    cfg = load_config(CONFIG)
    cfg.output.log_level = "ERROR"
    cfg.grid.N = N
    # Депрессия — ВСЕМ интервалам истории (их 72), иначе меняется только первый час
    for iv in cfg.time.history:
        iv.p_wf = pwf_MPa * 1e6
    if max_retries is not None:
        cfg.numerics.max_retries = max_retries
    sim, init = SimulatorFactory.from_config(cfg)

    calls = []  # (t, сут; dt, с; n_substeps) каждого вызова hydro.solve, включая повторные подшаги
    orig = sim._hydro.solve

    def logged(state, dt, bc):
        try:
            res = orig(state, dt, bc)
        except RuntimeError:
            calls.append((state.t / DAY, dt, None))   # отказ: лимит исчерпан
            raise
        calls.append((state.t / DAY, dt, res.n_substeps))
        return res

    sim._hydro.solve = logged
    try:
        hist = sim.run(init)
        return calls, hist.states[-1].p.copy(), None
    except RuntimeError as e:
        return calls, None, e


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
print(f"HEAD {head}; конфиг 03_standing_corey; лимит в прогонах — умолчание NumericsConfig", flush=True)
# Какой код считается: в worktree пакет и прототип обязаны быть из worktree (cwd), а не из основного каталога
print(f"пакет: {gpn_multiphase_solver.__file__}\nпрототип: {radial_blackoil.__file__}", flush=True)

summary = []
for N, pwf in CASES:
    t0 = time.perf_counter()
    calls, p_end, err = run(N, pwf)
    wall = time.perf_counter() - t0
    assert err is None, f"N={N} p_wf={pwf}: прогон при умолчании упал: {err}"
    n_max = max(c[2] for c in calls)
    k = int(np.log2(n_max))
    split = [c for c in calls if c[2] > 1]
    print(f"N={N} p_wf={pwf} МПа: вызовов гидро {len(calls)}, max n_substeps {n_max} -> k = {k}; "
          f"дроблёных вызовов {len(split)}; {wall:.1f} с", flush=True)
    for t, dt, n in split[:8]:
        print(f"    t = {t:.6f} сут, dt = {dt:.4g} с: {n} подшагов", flush=True)
    if len(split) > 8:
        print(f"    ... ещё {len(split) - 8}", flush=True)
    summary.append((N, pwf, k, p_end))

# Контроль минимальности: при k − 1 прогон обязан упасть; при k — совпасть с умолчанием побитно
print("\nКонтроль k − 1 и k:", flush=True)
for N, pwf, k, p_def in summary:
    if k == 0:
        continue
    calls, _, err = run(N, pwf, max_retries=k - 1)
    t_fail = calls[-1][0] if calls else float("nan")
    print(f"N={N} p_wf={pwf}: max_retries = {k - 1} -> "
          f"{'отказ при t = %.6f сут, вызов %d: %s' % (t_fail, len(calls), str(err)[:70]) if err else 'ПРОШЁЛ (минимальность опровергнута)'}",
          flush=True)
    _, p_k, err_k = run(N, pwf, max_retries=k)
    same = err_k is None and np.array_equal(p_k, p_def)
    print(f"N={N} p_wf={pwf}: max_retries = {k} -> "
          f"{'конечное p побитно как при умолчании' if same else 'РАСХОЖДЕНИЕ: ' + str(err_k)}", flush=True)
