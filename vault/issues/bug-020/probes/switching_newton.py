"""BUG-020: опытная четвёртая ступень advance — Ньютон с переключением набора фаз на итерациях.

Механизмы отказа (trace_stages, first_direction, trace_newton):
  М1 — первый шаг останова: забойная ячейка 0 (PV = 2.8e-3 м³) выше по потоку
       не стоит ни для одной грани, коэффициент запаса газа 1/Bg - Rs/Bo при
       51 бар мал; направление Ньютона |dSg_0| ~ 0.7 dt[с]. Граница -0.05 режет
       шаг до alpha ~ 1e-3, без границы S_g,0 уходит в -23…-2000, общий
       ограничитель |dSg| <= 0.2 масштабирует всё приращение и давление стоит.
  М2 — следующие шаги: смена ячейки «выше по потоку» в застойной зоне у забоя,
       Ньютон сходится линейно за ~26 итераций при лимите 15.

Опытная ступень (как в OPM Flow): поячеечное ограничение приращений
(|dp_i| <= dp_rel p_i, |dSg_i| <= ds_max), без линейного поиска; после каждой
итерации — переключение набора фаз: S_g < 0 -> однофазная, R_s из сохранения
отношения газ/нефть в ячейке; R_s > R_s^sat(p) -> двухфазная, S_g «закрытого
сосуда» (как blackoil.py:363-369). Сходимость — ||F||_inf <= допуск при
отсутствии переключений на последней итерации; лимит max_iter.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\switching_newton.py 20 10 B 24
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod, mode, t_end_h = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
DP_REL, DS_MAX, MAX_IT = 0.3, 0.2, 40
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"

cfg = load_config(BASE)
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
cfg.time.history = hist
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
n = model.grid.n
p_ext = cfg.initial_conditions.p0
ps0 = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                    sg=s.Sg.copy(), gas_active=(s.regime == 1))


def set_control():
    if mode == "A":
        model.set_bhp_control(p_ext / BAR_TO_PA)
    else:
        model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)


def newton_switching(state_old, dt, max_iter=MAX_IT, rtol=1e-8, atol=1e-11, trace=False):
    """Ньютон с переключением набора фаз на итерациях и поячеечным ограничением шага."""
    pvt = model.pvt
    mask = state_old.gas_active.copy()
    z = model.pack(state_old, mask)
    f_init = model.residual(z, state_old, dt, mask)
    scale = max(np.linalg.norm(f_init, np.inf), 1e-9)
    tol = atol + rtol * scale
    switched = 0
    total_sw = 0
    for it in range(1, max_iter + 1):
        J, f = model.finite_difference_jacobian(z, state_old, dt, mask)
        nrm = np.linalg.norm(f, np.inf)
        if trace:
            print(f"      it {it:2d}: |F| = {nrm:.2e}  2ф = {int(mask.sum())}  переключений {switched}  "
                  f"p0 = {z[0]:.2f}")
        if nrm <= tol and switched == 0:
            new = model.unpack(z, mask)
            tiny = mask & (new.sg < 0)
            new.sg[tiny] = 0.0
            return new, BlackOilNewtonReport(True, it - 1, float(nrm), phase_switches=total_sw)
        try:
            dz = model._linear_solve(J, -f)
        except Exception:
            return model.unpack(z, mask), BlackOilNewtonReport(False, it, float(nrm))
        p, x = z[:n], z[n:]
        dp, dx = dz[:n], dz[n:].copy()
        # ── поячеечное ограничение: давление (OPM dpMaxRel), S_g двухфазных (dsMax) ──
        lim = DP_REL * np.maximum(p, 1.0)
        dp = np.clip(dp, -lim, lim)
        dx = np.where(mask, np.clip(dx, -DS_MAX, DS_MAX), dx)
        pn = np.maximum(p + dp, 1.0 + 1e-6)
        xn = x + dx
        # однофазные: R_s не ниже нуля
        xn = np.where(mask, xn, np.maximum(xn, 0.0))
        # ── переключение набора фаз ──
        rs_sat = pvt.rs_sat(pn)
        deact = mask & (xn < -model.sg_switch_tol)
        act = (~mask) & (xn > rs_sat + model.rs_switch_tol)
        if np.any(deact):
            # сохранение отношения газ/нефть: R_s = R_s^sat + S_g Bo / ((1 - S_g) Bg)
            sg = xn[deact]
            pd = pn[deact]
            bo = pvt.bo(pd, rs_sat[deact])
            bg = pvt.bg(pd)
            xn[deact] = np.maximum(rs_sat[deact] + sg * bo / ((1.0 - sg) * bg), 0.0)
        if np.any(act):
            pa = pn[act]
            rtot = xn[act]
            rsat = rs_sat[act]
            bo = pvt.bo(pa, rsat)
            bg = pvt.bg(pa)
            d = np.maximum(rtot - rsat, 0.0)
            sg0 = np.maximum(d * bg / (bo + d * bg), 1e-8)
            if model.sg_activation_cap is not None:
                sg0 = np.minimum(sg0, model.sg_activation_cap)
            xn[act] = sg0
        mask = mask.copy()
        mask[deact] = False
        mask[act] = True
        switched = int(deact.sum() + act.sum())
        total_sw += switched
        z = np.concatenate([pn, xn])
    f = model.residual(z, state_old, dt, mask)
    return model.unpack(z, mask), BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)))


def advance4(state_old, dt):
    """Штатный advance; при отказе — опытная ступень (ветка скважины по старому состоянию)."""
    new, rep = model.advance(state_old, dt)
    if rep.converged:
        return new, rep, "штатно"
    if model.control_mode == "BHP":
        target = float(model.p_bhp_bar)
        model._well_branch = "shut" if float(state_old.pressure_bar[0]) <= target else "open"
    try:
        new, rep = newton_switching(state_old, dt)
    finally:
        model._well_branch = None
    if rep.converged and model.control_mode == "BHP":
        p0 = float(new.pressure_bar[0])
        target = float(model.p_bhp_bar)
        ok = p0 <= target if float(state_old.pressure_bar[0]) <= target else p0 >= target
        if not ok:
            rep.converged = False
    return new, rep, "ступень 4"


set_control()
print(f"=== {BASES[base_key]}: останов, режим {mode}, после {n_prod} сут; "
      f"ступень 4: dp_rel = {DP_REL}, ds_max = {DS_MAX}, max_iter = {MAX_IT} ===")

# ── 1. Первый шаг: опытная ступень одна, без штатных, при разных dt ──
print("\n1. Первый шаг останова, только опытная ступень:")
for dt in (60.0, 169.0, 600.0, 3600.0, 86400.0):
    set_control()
    if mode == "A":
        model._well_branch = "shut"
    t1 = time.perf_counter()
    new, rep = newton_switching(ps0, dt)
    model._well_branch = None
    el = time.perf_counter() - t1
    if rep.converged:
        bal = model.step_global_balance(ps0, new, dt)
        print(f"   dt = {dt:7.0f} с: ✓ it = {rep.iterations:2d}, переключений {rep.phase_switches}, "
              f"p0 = {new.pressure_bar[0]:7.2f} бар, 2ф = {int(new.gas_active.sum())}, "
              f"min Sg = {new.sg[new.gas_active].min() if new.gas_active.any() else 0:.4f}, "
              f"баланс (нефть, газ) = ({bal[0]:+.1e}, {bal[1]:+.1e}) м³ст ({el:.1f} с)")
    else:
        print(f"   dt = {dt:7.0f} с: ✗ it = {rep.iterations}, res = {rep.residual_inf:.1e} ({el:.1f} с)")
        newton_switching(ps0, dt, trace=True)

# ── 2. Согласие со штатным решением, где штатный сходится (dt = 60 с) ──
set_control()
ref, rr = model.advance(ps0, 60.0)
if mode == "A":
    model._well_branch = "shut"
alt, ra = newton_switching(ps0, 60.0)
model._well_branch = None
if rr.converged and ra.converged:
    same_mask = bool(np.array_equal(ref.gas_active, alt.gas_active))
    print(f"\n2. dt = 60 с, штатный против опытной: маски совпадают: {same_mask}; "
          f"max|dp| = {np.abs(ref.pressure_bar - alt.pressure_bar).max():.2e} бар, "
          f"max|dSg| = {np.abs(ref.sg - alt.sg).max():.2e}, max|dRs| = {np.abs(ref.rs_sm3_sm3 - alt.rs_sm3_sm3).max():.2e}")

# ── 3. Лестница шагов со ступенью 4 ──
print(f"\n3. Лестница (первый шаг 60 с, рост ×2 до 1 сут, отказ ÷2) до {t_end_h} ч:")
set_control()
ps, t, dt = ps0, 0.0, 60.0
n_acc = n_rej = n_st4 = 0
t1 = time.perf_counter()
while t < t_end_h * 3600.0 - 1e-6:
    step = min(dt, t_end_h * 3600.0 - t)
    new, rep, how = advance4(ps, step)
    if rep.converged:
        ps, t = new, t + step
        n_acc += 1
        n_st4 += how == "ступень 4"
        if n_acc <= 10 or n_acc % 5 == 0 or t >= t_end_h * 3600.0 - 1e-6:
            print(f"   ✓ t = {t/3600:8.3f} ч  dt = {step:8.1f} с  {how:9s} it = {rep.iterations:2d}  "
                  f"p0 = {ps.pressure_bar[0]:7.2f} бар  2ф = {int(ps.gas_active.sum())}  max Sg = {ps.sg.max():.4f}")
        dt = min(step * 2.0, DAY)
    else:
        n_rej += 1
        print(f"   ✗ t = {t/3600:8.3f} ч  dt = {step:8.1f} с  {how}: it = {rep.iterations}, res = {rep.residual_inf:.1e}")
        dt = step / 2.0
        if dt < 1e-3:
            break
print(f"   итог: {t/3600:.2f} ч за {n_acc} шагов ({n_st4} — ступенью 4), {n_rej} отказов, "
      f"{time.perf_counter() - t1:.1f} с; p0 = {ps.pressure_bar[0]:.2f} бар, 2ф = {int(ps.gas_active.sum())}")
