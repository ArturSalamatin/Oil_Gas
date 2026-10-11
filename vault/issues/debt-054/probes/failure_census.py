"""DEBT-054, проба планирования: что покажет отчёт отказа с мерой ячеек и абсолютным допуском.

Код прототипа не меняется: обёртки вокруг _newton_fixed_active_set и _newton_switching
пересчитывают по возвращённому приближению абсолютный допуск tol = atol + rtol*max(||F0||, 1e-9)
и меру условия ячейки max_c |F_c,i|*dt/PV_i — то, что план положит в BlackOilNewtonReport.
Отказ адаптера (HydroConvergenceError) классифицируется по отчёту, который он печатает:
после подмены DEBT-030 — последний Ньютон ступени 1, при ступени 4 по памяти — её Ньютон.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-054\\probes\\failure_census.py
"""
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

# Код — из каталога запуска (основной или worktree), а не из установки в общий venv:
# иначе в worktree проба молча считает код основного каталога (reference_worktree_pythonpath)
SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
print(f"SOLVER = {SOLVER}")

from gpn_multiphase_solver.factory import SimulatorFactory          # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config             # noqa: E402
import gpn_multiphase_solver                                         # noqa: E402
import radial_blackoil                                               # noqa: E402

print(f"gpn_multiphase_solver: {Path(gpn_multiphase_solver.__file__).parent}")
print(f"radial_blackoil:       {Path(radial_blackoil.__file__).parent}")


def _stage(m):
    """Ступень advance по флагам модели: 4 — _phase_switching, 3 — L2-поиск, 2 — без границы Sg, 1."""
    if m._phase_switching:
        return 4
    if m._line_search_l2:
        return 3
    if m._sg_lower_bound is None:
        return 2
    return 1


def instrument(model):
    """Обёртки обоих Ньютонов; записи — в model._census (список словарей)."""
    model._census = []
    n = model.grid.n
    # Счётчики внутри одного решения Ньютона: построенные якобианы и исключения
    # линейного решателя — по ним выводится причина выхода, которой отчёт пока не знает
    cnt = {"jac": 0, "lin_exc": 0}
    orig_jac = model.finite_difference_jacobian
    orig_lin = model._linear_solve

    def jac(*a, **kw):
        cnt["jac"] += 1
        return orig_jac(*a, **kw)

    def lin(*a, **kw):
        try:
            return orig_lin(*a, **kw)
        except Exception:
            cnt["lin_exc"] += 1
            raise

    model.finite_difference_jacobian = jac
    model._linear_solve = lin

    def measure(f, state_old, dt_s):
        w = dt_s / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, state_old.pressure_bar)
        return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))

    orig_fas = model._newton_fixed_active_set

    def fas(z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
        f0 = model.residual(z0, state_old, dt_s, gas_active)
        tol = atol_sm3s + rtol * max(float(np.linalg.norm(f0, np.inf)), 1e-9)
        cnt["jac"] = cnt["lin_exc"] = 0
        z, rep = orig_fas(z0, state_old, dt_s, gas_active, max_iter=max_iter, rtol=rtol,
                          atol_sm3s=atol_sm3s)
        f = model.residual(z, state_old, dt_s, gas_active)
        # Причина выхода: исключение решателя; сходимость; иначе линейный поиск или лимит
        # (на итерации max_iter их не различить: оба дают iterations = max_iter)
        if cnt["lin_exc"]:
            why = "linear_solver"
        elif rep.converged:
            why = "converged"
        elif rep.iterations < max_iter:
            why = "line_search"
        else:
            why = "max_iter|line_search"
        model._census.append(dict(
            kind="fas", stage=_stage(model), branch=model._well_branch, conv=rep.converged,
            it=rep.iterations, res=rep.residual_inf, res_z=float(np.linalg.norm(f, np.inf)),
            tol=tol, meas=measure(f, state_old, dt_s), max_iter=max_iter, jac=cnt["jac"],
            why=why))
        return z, rep

    orig_sw = model._newton_switching

    def sw(state_old, dt_s, *a, **kw):
        z0 = model.pack(state_old, state_old.gas_active)
        f0 = model.residual(z0, state_old, dt_s, state_old.gas_active)
        tol = 1e-11 + 1e-8 * max(float(np.linalg.norm(f0, np.inf)), 1e-9)
        cnt["jac"] = cnt["lin_exc"] = 0
        new, rep = orig_sw(state_old, dt_s, *a, **kw)
        f = model.residual(model.pack(new, new.gas_active), state_old, dt_s, new.gas_active)
        # Якобиан строится в начале каждого прохода it = 1..41: выход на проходе it —
        # it якобианов. Лимит — 41 (it > max_iter); меньше без сходимости — обрыв
        # (решатель или нечисловое), или отказ по S_g > 0.98 (converged = False на сходимости)
        if cnt["lin_exc"]:
            why = "linear_solver"
        elif rep.converged:
            why = "converged"
        elif cnt["jac"] >= 41:
            why = "max_iter"
        else:
            why = "nonfinite|sg_bound"
        model._census.append(dict(
            kind="sw", stage=4, branch=model._well_branch, conv=rep.converged,
            it=rep.iterations, res=rep.residual_inf, res_z=float(np.linalg.norm(f, np.inf)),
            tol=tol, meas=measure(f, state_old, dt_s), max_iter=40, jac=cnt["jac"], why=why))
        return new, rep

    model._newton_fixed_active_set = fas
    model._newton_switching = sw


def classify(rec, cell_tol):
    a = rec["res"] <= rec["tol"]
    c = cell_tol is None or rec["meas"] <= cell_tol
    return {(True, False): "только ячейка", (False, True): "только абсолютное",
            (False, False): "оба не выполнены", (True, True): "оба выполнены"}[(a, c)]


def wrap_adapter(sim, failures):
    """Каждый отказ адаптера: текст ошибки, записи Ньютонов этого вызова."""
    model = sim._hydro._model
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        start = len(model._census)
        try:
            return orig(state, dt, bc)
        except HydroConvergenceError as exc:
            failures.append(dict(msg=str(exc), recs=model._census[start:], dt=dt, t=state.t))
            raise

    sim._hydro.solve = solve


def reported(f):
    """Запись Ньютона, чей отчёт печатает адаптер: ступень 4 по памяти — её, иначе последняя ступени 1."""
    recs = f["recs"]
    if "по памяти" in f["msg"]:
        return [r for r in recs if r["stage"] == 4][-1]
    return [r for r in recs if r["stage"] == 1][-1]


def fmt(r, cell_tol):
    return (f"ступень {r['stage']} {r['kind']} ветвь={r['branch']} сошлось={r['conv']} "
            f"итераций {r['it']}/{r['max_iter']} якобианов {r['jac']} выход {r['why']} "
            f"невязка {r['res']:.3e} (по z {r['res_z']:.3e}) "
            f"допуск {r['tol']:.3e} мера ячеек {r['meas']:.3e} порог {cell_tol} -> "
            f"{classify(r, cell_tol)}")


# ── 1. Сценарий воспроизведения: BUG-018, N = 350, один вызов адаптера dt = 86400 с ──
print("\n=== 1. BUG-018, N = 350, один вызов адаптера ===")
cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
cfg.output.log_level = "ERROR"
cfg.grid.N = 350
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
instrument(model)
_, dt = sim._schedule.substeps(0)
try:
    sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
    print("сошлось (неожиданно)")
except HydroConvergenceError as exc:
    print(f"отказ: {exc}")
for r in model._census:
    print("  " + fmt(r, model.cell_tol))

# ── 2. Тот же сценарий через Simulator: первые сутки дроблением ──
print("\n=== 2. BUG-018, N = 350, Simulator.run ===")
sim, init = SimulatorFactory.from_config(cfg)
instrument(sim._hydro._model)
failures = []
wrap_adapter(sim, failures)
t0 = time.perf_counter()
sim.run(init)
print(f"время {time.perf_counter() - t0:.1f} с, отказов адаптера {len(failures)}")
for f in failures:
    print(f"  {f['msg']}")
    print("    печатаемый отчёт: " + fmt(reported(f), sim._hydro._model.cell_tol))

def census(sim, init, title):
    """Перепись отказов адаптера за весь расчёт: классы печатаемого отчёта и всех отказавших Ньютонов."""
    print(f"\n=== {title} ===")
    instrument(sim._hydro._model)
    failures = []
    wrap_adapter(sim, failures)
    t0 = time.perf_counter()
    sim.run(init)
    ct = sim._hydro._model.cell_tol
    print(f"время {time.perf_counter() - t0:.1f} с, отказов адаптера {len(failures)}, cell_tol = {ct}")
    cls = Counter((("память" if "по памяти" in f["msg"] else "advance"), classify(reported(f), ct))
                  for f in failures)
    print(f"  классы печатаемого отчёта (путь, класс): {dict(cls)}")
    for f in failures[:8]:
        print(f"  {f['msg']}")
        print("    печатаемый отчёт: " + fmt(reported(f), ct))
    allc = Counter((r["stage"], classify(r, ct)) for f in failures for r in f["recs"] if not r["conv"])
    print(f"  отказавшие Ньютоны (ступень, класс): {dict(sorted(allc.items()))}")


# ── 4. Суточный останов (TestDailyShutin): 10 сут добычи + 3 сут q_oil = 0, ступень 4 по памяти ──
if "--shutin" in sys.argv:
    import copy
    cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
    cfg.output.log_level = "ERROR"
    hist = list(cfg.time.history)
    for _ in range(3):
        x = copy.deepcopy(hist[0])
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    sim, init = SimulatorFactory.from_config(cfg)
    census(sim, init, "4. Суточный останов bug020_rs300 (TestDailyShutin)")
    sys.exit(0)

# ── 3. Перепись отказов на примерах ──
for name in sys.argv[1:] or ["14_high_gor_cooling", "17_shut_in_strong_cooling"]:
    print(f"\n=== 3. Пример {name} ===")
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    instrument(sim._hydro._model)
    failures = []
    wrap_adapter(sim, failures)
    t0 = time.perf_counter()
    sim.run(init)
    ct = sim._hydro._model.cell_tol
    print(f"время {time.perf_counter() - t0:.1f} с, отказов адаптера {len(failures)}, cell_tol = {ct}")
    cls = Counter(classify(reported(f), ct) for f in failures)
    print(f"  классы печатаемого отчёта: {dict(cls)}")
    for f in failures[:5]:
        print(f"  {f['msg']}")
        print("    печатаемый отчёт: " + fmt(reported(f), ct))
    # По всем отказавшим Ньютонам всех ступеней — как часто отказ «только по ячейке»
    allc = Counter((r["stage"], classify(r, ct)) for f in failures for r in f["recs"] if not r["conv"])
    print(f"  отказавшие Ньютоны (ступень, класс): {dict(sorted(allc.items()))}")
