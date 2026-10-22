"""BUG-020: числа для тестов плана на замороженных сценариях data/bug020_rs300.json, bug020_rs150.json.

Сценарии — будущие tests/data/bug020_rs300/config.json и bug020_rs150/config.json
(копии конфигов примеров 20 и 19 на 2026-10-06 с историей 10 сут добычи; у
rs150 — плюс час останова q_oil = 0). Правка прототипа — plan_code.apply.

A. rs300, уровень модели: шаг останова 168.75 с без ступени 4 и с ней (режимы
   B и A), тот же корень при 60 с, баланс масс, согласованность фаз, время.
B. rs150, уровень адаптера: первый час останова без ступени 4 и с ней.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\plan_tests_check.py
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (HERE, SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402
import plan_code  # noqa: E402

BAR = 1e5
ATM_BAR = 101325.0 / BAR

# ── A. rs300 ──
cfg = load_config(HERE / "data" / "bug020_rs300.json")
sim, init = SimulatorFactory.from_config(cfg)
t1 = time.perf_counter()
h = sim.run(init)
print(f"A. rs300: записей {len(h.states)}, t = {h.states[-1].t/86400:.1f} сут; добыча {time.perf_counter()-t1:.1f} с")
s = h.states[-1]
ps = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(), gas_active=(s.regime == 1))
print(f"   состояние: p0 = {ps.pressure_bar[0]:.4f} бар, 2ф = {int(ps.gas_active.sum())}, max Sg = {ps.sg.max():.4f}")
model = sim._hydro._model
p_ext_bar = cfg.initial_conditions.p0 / BAR
DT = 168.75

model.set_oil_rate_control(0.0, ATM_BAR)
t1 = time.perf_counter()
new, rep = model.advance(ps, DT)
print(f"   без ступени 4, B, dt = {DT}: сошлось {rep.converged} ({time.perf_counter()-t1:.1f} с)")
model.set_bhp_control(p_ext_bar)
new, rep = model.advance(ps, DT)
print(f"   без ступени 4, A, dt = {DT}: сошлось {rep.converged}")
model.set_oil_rate_control(0.0, ATM_BAR)
ref60, r60 = model.advance(ps, 60.0)

plan_code.apply(model)
model.set_oil_rate_control(0.0, ATM_BAR)
t1 = time.perf_counter()
new, rep = model.advance(ps, DT)
el = time.perf_counter() - t1
bo, bg = model.step_global_balance(ps, new, DT)
oi, gi = model.component_inventories(new)
rs_sat = model.pvt.rs_sat(new.pressure_bar)
one = ~new.gas_active
print(f"   со ступенью 4, B: сошлось {rep.converged}, ступень 4 {getattr(rep, 'phase_switching', False)}, "
      f"итераций {rep.iterations}, переключений {rep.phase_switches}; p0 = {new.pressure_bar[0]:.4f} бар, "
      f"2ф = {int(new.gas_active.sum())}, max Sg = {new.sg.max():.4f}; баланс {bo/oi.sum():.1e}/{bg/gi.sum():.1e}; "
      f"min Sg 2ф = {new.sg[new.gas_active].min():.3e}; max(Rs - Rs_sat) 1ф = "
      f"{np.max(new.rs_sm3_sm3[one] - rs_sat[one]):.2e}; {el:.1f} с")
model.set_bhp_control(p_ext_bar)
t1 = time.perf_counter()
newA, repA = model.advance(ps, DT)
print(f"   со ступенью 4, A: сошлось {repA.converged}, ветка '{repA.well_branch}', ступень 4 "
      f"{getattr(repA, 'phase_switching', False)}, p0 = {newA.pressure_bar[0]:.4f} бар, 2ф = {int(newA.gas_active.sum())}; "
      f"{time.perf_counter()-t1:.1f} с; |p0(A) - p0(B)| = {abs(newA.pressure_bar[0]-new.pressure_bar[0]):.2e} бар")
model.set_oil_rate_control(0.0, ATM_BAR)
alt, ra = model._newton_switching(ps, 60.0)
print(f"   dt = 60 с: штатный {r60.converged}, ступень 4 отдельно {ra.converged}; маски равны "
      f"{np.array_equal(ref60.gas_active, alt.gas_active)}; max|Δp| = {np.abs(ref60.pressure_bar-alt.pressure_bar).max():.2e} бар; "
      f"max|ΔSg| = {np.abs(ref60.sg-alt.sg).max():.2e}; max|ΔRs| = {np.abs(ref60.rs_sm3_sm3-alt.rs_sm3_sm3).max():.2e}")
print(f"   атрибуты после шагов: _upwind_frozen = {model._upwind_frozen}, _phase_switching = {model._phase_switching}")

# ── B. rs150 ──
for use4 in (False, True):
    cfg = load_config(HERE / "data" / "bug020_rs150.json")
    sim, init = SimulatorFactory.from_config(cfg)
    if use4:
        plan_code.apply(sim._hydro._model)
    calls = []
    orig = sim._hydro.solve

    def solve(state, dt, bc, orig=orig, calls=calls):
        r = orig(state, dt, bc)
        calls.append((state.t, dt, r.n_substeps))
        return r

    sim._hydro.solve = solve
    t1 = time.perf_counter()
    try:
        hh = sim.run(init)
        st = hh.states[-1]
        first = [c for c in calls if c[0] >= 10 * 86400.0 - 1e-6][0]
        tail = (f"✓ подшагов первого часа {first[2]}; p0 = {st.p[0]/BAR:.4f} бар, "
                f"2ф = {int(np.count_nonzero(st.regime == 1))}, max Sg = {st.Sg.max():.4f}, "
                f"T0 = {st.T[0]:.4f} К; записей {len(hh.states)}")
    except RuntimeError as e:
        tail = f"✗ {str(e)[:70]}"
    print(f"B. rs150, ступень 4 {'да' if use4 else 'нет'}: {tail} ({time.perf_counter()-t1:.1f} с)")
