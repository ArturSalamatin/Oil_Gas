"""DEBT-054, проба планирования: сценарии будущих тестов на текущем коде (до правки).

Проверяет допущения плана: на каких сценариях какой выход Ньютона, какие числа.
Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-054\\probes\\test_scenarios.py
"""
import sys
from pathlib import Path

import numpy as np

# Код — из каталога запуска (основной или worktree), а не из установки в общий venv
SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
print(f"SOLVER = {SOLVER}")

import radial_blackoil  # noqa: E402
print(f"radial_blackoil: {Path(radial_blackoil.__file__).parent}")
from tests.test_prototype_cell_tolerance import (  # noqa: E402
    _build, _measure, CELL_TOL, DT, DT_STAGE4, RS300, ATM_BAR, BAR)
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config     # noqa: E402
from radial_blackoil.state import BlackOilState              # noqa: E402

# ── 1. pack(unpack(z)) — побитовое тождество (мера по z равна мере теста) ──
model, state = _build(12, cell_tol=CELL_TOL)
z, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)
print(f"\n1. N=12 cell_tol: converged={rep.converged} it={rep.iterations} res={rep.residual_inf:.3e}")
zz = model.pack(model.unpack(z, state.gas_active), state.gas_active)
print(f"   pack(unpack(z)) == z побитово: {np.array_equal(zz, z)}")
f = model.residual(z, state, DT, state.gas_active)
w = model._cell_weights(state, DT)
n = model.grid.n
m_code = max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))
m_test = _measure(model, state, model.unpack(z, state.gas_active), DT)
print(f"   мера по f кода {m_code!r}, мера теста {m_test!r}, равны: {m_code == m_test}")
f0 = model.residual(model.pack(state), state, DT, state.gas_active)
tol = 1e-11 + 1e-8 * max(float(np.linalg.norm(f0, np.inf)), 1e-9)
print(f"   допуск {tol!r}")

# ── 2. max_iter = 1: выход по лимиту, не по линейному поиску ──
model, state = _build(12, cell_tol=CELL_TOL)
z, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active, max_iter=1)
f = model.residual(z, state, DT, state.gas_active)
print(f"\n2. max_iter=1: converged={rep.converged} it={rep.iterations} res={rep.residual_inf:.3e} "
      f"z сдвинулся от старта: {not np.array_equal(z, model.pack(state))}")

# ── 3. Исключение линейного решателя на первой итерации ──
model, state = _build(12, cell_tol=CELL_TOL)
def boom(*a, **kw):
    raise np.linalg.LinAlgError("проба")
model._linear_solve = boom
z, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)
f0 = model.residual(model.pack(state), state, DT, state.gas_active)
print(f"\n3. линейный решатель: converged={rep.converged} it={rep.iterations} "
      f"res={rep.residual_inf!r} ||F0||={float(np.linalg.norm(f0, np.inf))!r}")

# ── 4. _advance_phases с max_active_iter = 1 при появлении газа (N = 50) ──
for N in (12, 50):
    model, state = _build(N, cell_tol=CELL_TOL)
    new, rep = model._advance_phases(state, DT, max_active_iter=1)
    print(f"\n4. N={N} max_active_iter=1: converged={rep.converged} it={rep.iterations} "
          f"aset={rep.active_set_iterations} switches={rep.phase_switches} res={rep.residual_inf:.3e}")
    model, state = _build(N, cell_tol=CELL_TOL)
    new, rep = model._advance_phases(state, DT)
    print(f"   штатно: converged={rep.converged} aset={rep.active_set_iterations} "
          f"switches={rep.phase_switches}")

# ── 5. Ступень 4 на останове rs300: 1e-30 — абсолютное выполнено? ──
cfg = load_config(RS300)
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
model.set_oil_rate_control(0.0, ATM_BAR)
ps = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(),
                   gas_active=(s.regime == 1))
z0 = model.pack(ps, ps.gas_active)
f0 = model.residual(z0, ps, DT_STAGE4, ps.gas_active)
tol4 = 1e-11 + 1e-8 * max(float(np.linalg.norm(f0, np.inf)), 1e-9)
for ct in (CELL_TOL, 1e-30):
    model.cell_tol = ct
    new, rep = model._newton_switching(ps, DT_STAGE4)
    print(f"\n5. ступень 4, cell_tol={ct}: converged={rep.converged} it={rep.iterations} "
          f"res={rep.residual_inf:.3e} допуск={tol4:.3e} абс. выполнено={rep.residual_inf <= tol4} "
          f"мера={_measure(model, ps, new, DT_STAGE4):.3e}")
model.cell_tol = CELL_TOL

# ── 6. Ступень 4: обрыв по линейному решателю на 3-м вызове — что пишет отчёт сейчас ──
orig = model._linear_solve
k = {"n": 0}
def third(*a, **kw):
    k["n"] += 1
    if k["n"] == 3:
        raise np.linalg.LinAlgError("проба")
    return orig(*a, **kw)
model._linear_solve = third
new, rep = model._newton_switching(ps, DT_STAGE4)
print(f"\n6. ступень 4, отказ решателя на 3-м вызове: converged={rep.converged} it={rep.iterations} "
      f"(после правки ожидается 2) res={rep.residual_inf:.3e}")
# ── 7. Нечисловое направление на 2-м вызове ──
k["n"] = 0
def nan2(*a, **kw):
    k["n"] += 1
    dz = orig(*a, **kw)
    if k["n"] == 2:
        dz = dz.copy(); dz[0] = np.nan
    return dz
model._linear_solve = nan2
new, rep = model._newton_switching(ps, DT_STAGE4)
print(f"7. ступень 4, NaN в направлении на 2-м вызове: converged={rep.converged} it={rep.iterations} "
      f"(после правки ожидается 1) res={rep.residual_inf:.3e}")
model._linear_solve = orig
