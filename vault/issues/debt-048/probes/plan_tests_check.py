"""DEBT-048: ожидания тестов плана на реальном шаге останова (код базы не меняется).

Сценарий rs300 (numerical_solver/tests/data/bug020_rs300): 10 сут добычи при 5 МПа,
затем шаги останова q_oil = 0 по DT = 168.75 с (шаг теста BUG-020, где ступени 1-3 не сходятся).
  1. Ступень 4 отдельно (эмуляция advance_fourth_stage: _phase_switching + _fallback,
     как install_memory пробы stage_memory.py) против advance с того же состояния: побитово ли.
  2. Цепочка из N_STEPS шагов через адаптер: без памяти и с памятью m2s (эмуляция на модели).
     Какая ступень решила каждый шаг, совпадают ли состояния побитово.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-048\\probes\\plan_tests_check.py
"""

import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_memory as sm  # noqa: E402  (подключает numerical_solver и прототип к sys.path)

from gpn_multiphase_solver.bc import RateControl  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

DT = 168.75
N_STEPS = 6
BAR = 1e5
out = sm.Tee(HERE / f"plan_tests_check{sm.TAG}.out.txt")   # DEBT048_TAG — как у stage_memory.py


def proto(s):
    """SimulationState (Па) -> BlackOilState (бар), как адаптер."""
    return BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(),
                         sg=s.Sg.copy(), gas_active=(s.regime == 1))


def stage4_only(model, ps, dt):
    model._phase_switching = True
    try:
        new, rep = model._fallback(ps, dt, 12, 15)
        rep.globalized = True; rep.phase_switching = True
    finally:
        model._phase_switching = False
    return new, rep


def same(a, b):
    return all(np.array_equal(getattr(a, f), getattr(b, f)) for f in ("p", "Sg", "Rs", "regime"))


t0 = time.perf_counter()
cfg = load_config(sm.SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
s0 = sim.run(init).states[-1]
adapter, model = sim._hydro, sim._hydro._model
bc = replace(sim._schedule.intervals[-1].bc, well=RateControl(0.0, 101325.0))
out(sm.code_paths())
out(f"10 сут добычи: {time.perf_counter() - t0:.1f} с; p(r_w) = {s0.p[0] / BAR:.4f} бар, "
    f"двухфазных {int(np.count_nonzero(s0.regime == 1))}, max S_g = {s0.Sg.max():.4f}")

# ── 1. Ступень 4 отдельно против advance (один шаг с s0) ──
model.set_oil_rate_control(0.0, 101325.0 / BAR)
ps = proto(s0)
t1 = time.perf_counter()
a, ra = model.advance(ps, DT)
b, rb = stage4_only(model, ps, DT)
eq = all(np.array_equal(getattr(a, f), getattr(b, f))
         for f in ("pressure_bar", "sg", "rs_sm3_sm3", "gas_active"))
out(f"1. шаг {DT} с: advance — сошёлся {ra.converged}, ступень 4 {ra.phase_switching}, "
    f"итераций {ra.iterations}, ветка '{ra.well_branch}'; ступень 4 отдельно — сошлась {rb.converged}, "
    f"итераций {rb.iterations}; состояния побитово {eq}; отчёт: невязка {ra.residual_inf:.3e} / "
    f"{rb.residual_inf:.3e}; {time.perf_counter() - t1:.1f} с")

# ── 2. Цепочка через адаптер: без памяти, затем с памятью m2s ──
chains = {}
for variant in ("0", "m2s"):
    if variant != "0":
        sm.install(model, variant)       # подмена advance на экземпляре (m2s: M = 2, строгий)
    inner, reps = model.advance, []

    def rec(ps_, dt_, *a, **kw):
        new, rep = inner(ps_, dt_, *a, **kw)
        reps.append(rep)
        return new, rep

    model.advance = rec
    sm.MEM.clear()
    steps, s = [], s0
    t1 = time.perf_counter()
    for k in range(N_STEPS):
        before = dict(sm.MEM)
        r = adapter.solve(s, DT, bc)     # отказ — HydroConvergenceError: проба остановится
        first4 = sm.MEM.get("first4", 0) > before.get("first4", 0)
        steps.append((r.state, first4, reps[-1]))
        s = r.state
    chains[variant] = steps
    del model.advance                    # вернуть метод класса
    out(f"2. {variant}: {N_STEPS} шагов по {DT} с, {time.perf_counter() - t1:.1f} с; "
        f"ступень 4 по памяти на шагах {[k + 1 for k, (_, f, _r) in enumerate(steps) if f]}; "
        f"решила ступень 4 (phase_switching): {[bool(rr.phase_switching) for _, _, rr in steps]}; "
        f"итераций: {[int(rr.iterations) for _, _, rr in steps]}")
for k in range(N_STEPS):
    s_a, s_b = chains["0"][k][0], chains["m2s"][k][0]   # (состояние, по памяти, отчёт)
    out(f"   шаг {k + 1}: побитово {same(s_a, s_b)}; p(r_w) = {s_a.p[0] / BAR:.6f} бар, "
        f"двухфазных {int(np.count_nonzero(s_a.regime == 1))}")
out(f"всего {time.perf_counter() - t0:.1f} с")
