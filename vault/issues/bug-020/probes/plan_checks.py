"""BUG-020: проверки кода плана (plan_code) — заготовки тестов.

1. Побитовость: шаг, который решают штатные ступени, с правкой и без неё одинаков.
2. Ступень 4 отдельно на первом шаге останова при разных dt (режимы A и B).
3. Тот же корень: где штатный advance сходится (dt = 60 с), ступень 4 даёт то же решение.
4. Переключение фаз сохраняет отношение газ/нефть ячейки (в обе стороны).
5. Баланс масс шага ступени 4 (step_global_balance).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\plan_checks.py
"""

import copy
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (HERE, SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402
import plan_code  # noqa: E402

DAY = 86400.0
cfg = load_config(SOLVER / "examples" / "20_rs300_cooling" / "config.json")
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(10):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
cfg.time.history = hist
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
p_ext_bar = cfg.initial_conditions.p0 / BAR_TO_PA
p_wf_bar = iv.p_wf / BAR_TO_PA
ps0 = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                    sg=s.Sg.copy(), gas_active=(s.regime == 1))
print(f"10 сут добычи конфига 20: p0 = {ps0.pressure_bar[0]:.2f} бар, 2ф = {int(ps0.gas_active.sum())}")

# ── 1. Побитовость на шагах, которые решают штатные ступени ──
model.set_bhp_control(p_wf_bar)
ref_prod, r1 = model.advance(ps0, 3600.0)
model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)
ref_60, r2 = model.advance(ps0, 60.0)
plan_code.apply(model)
model.set_bhp_control(p_wf_bar)
new_prod, r3 = model.advance(ps0, 3600.0)
model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)
new_60, r4 = model.advance(ps0, 60.0)


def same(a, b):
    return all(np.array_equal(getattr(a, f), getattr(b, f)) for f in ("pressure_bar", "rs_sm3_sm3", "sg", "gas_active"))


print(f"1. побитово: добыча 3600 с — {same(ref_prod, new_prod)} (сошлось {r1.converged}/{r3.converged}); "
      f"останов 60 с — {same(ref_60, new_60)} (ступень 4: {getattr(r4, 'phase_switching', False)})")

# ── 2. Ступень 4 отдельно, первый шаг останова ──
for mode in ("B", "A"):
    if mode == "A":
        model.set_bhp_control(p_ext_bar)
    else:
        model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)
    row = []
    for dt in (60.0, 120.0, 168.75, 240.0, 337.5, 675.0, 1350.0, 3600.0):
        model._well_branch = "shut" if mode == "A" else None
        new, rep = model._newton_switching(ps0, dt)
        model._well_branch = None
        row.append(f"{dt:g}:{'✓' + str(rep.iterations) if rep.converged else '✗'}")
    print(f"2. режим {mode}, только ступень 4 (dt:итог/итерации): " + "  ".join(row))

# ── 3. Тот же корень, что у штатного алгоритма (dt = 60 с, режим B) ──
model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)
alt, ra = model._newton_switching(ps0, 60.0)
print(f"3. dt = 60 с: штатный {r2.converged}, ступень 4 {ra.converged} ({ra.iterations} ит.); маски равны: "
      f"{np.array_equal(ref_60.gas_active, alt.gas_active)}; max|Δp| = "
      f"{np.abs(ref_60.pressure_bar - alt.pressure_bar).max():.2e} бар, "
      f"max|ΔSg| = {np.abs(ref_60.sg - alt.sg).max():.2e}, max|ΔRs| = {np.abs(ref_60.rs_sm3_sm3 - alt.rs_sm3_sm3).max():.2e}")

# ── 4. Переключение фаз сохраняет отношение газ/нефть ──
pvt = model.pvt
n = model.grid.n
p = ps0.pressure_bar.copy()
rs_sat = pvt.rs_sat(p)
# двухфазные ячейки с S_g < 0 -> однофазные
mask = np.ones(n, bool)
sg_neg = -np.linspace(0.01, 0.5, n)
bo = pvt.bo(p, rs_sat)
bg = pvt.bg(p)
ratio_before = ((1 - sg_neg) * rs_sat / bo + sg_neg / bg) / ((1 - sg_neg) / bo)
x, m, ns = model._switch_phases(p, sg_neg, mask)
ok = ~m & (ratio_before > 0)
err_d = np.max(np.abs(x[ok] - ratio_before[ok]) / np.maximum(ratio_before[ok], 1.0))
# однофазные с R_s > R_s^sat -> двухфазные; отношение газ/нефть двухфазного состояния = R_s до переключения
mask = np.zeros(n, bool)
rs_hi = rs_sat * 1.05 + 1.0
x2, m2, _ = model._switch_phases(p, rs_hi, mask)
sg = x2
capped = (model.sg_activation_cap is not None) & (sg >= (model.sg_activation_cap or 1.0))
ratio_after = ((1 - sg) * rs_sat / bo + sg / bg) / ((1 - sg) / bo)
err_a = np.max(np.abs(ratio_after[~capped] - rs_hi[~capped]) / rs_hi[~capped])
print(f"4. переключение: деактивировано {int((~m).sum())}/{n}, max отн. ошибка отношения газ/нефть {err_d:.1e}; "
      f"активировано {int(m2.sum())}/{n}, ошибка {err_a:.1e} (с ограничением BUG-018: {int(capped.sum())})")

# ── 5. Баланс масс шага ступени 4 ──
model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)
new, rep = model.advance(ps0, 337.5)
if rep.converged:
    bo_, bg_ = model.step_global_balance(ps0, new, 337.5)
    oi, gi = model.component_inventories(new)
    print(f"5. dt = 337.5 с: ступень 4 = {getattr(rep, 'phase_switching', False)}, баланс нефть "
          f"{bo_ / oi.sum():.1e}, газ {bg_ / gi.sum():.1e} (доля запаса); S_g >= 0: {bool(np.all(new.sg >= 0))}; "
          f"R_s однофазных <= R_s^sat + tol: {bool(np.all(new.rs_sm3_sm3[~new.gas_active] <= pvt.rs_sat(new.pressure_bar[~new.gas_active]) + model.rs_switch_tol))}")
else:
    print(f"5. dt = 337.5 с: отказ, res = {rep.residual_inf:.1e}")
