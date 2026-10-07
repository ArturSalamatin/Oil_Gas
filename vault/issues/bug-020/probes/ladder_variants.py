"""BUG-020: варианты четвёртой ступени advance на лестнице шагов останова.

Добыча n_prod суток, затем останов (A: p_wf = p_ext; B: q_oil = 0) лестницей:
первый шаг 60 с, рост ×2 до 1 сут, отказ — ÷2; штатный advance, при его отказе —
четвёртая ступень по варианту:
  V0 — нет (штатный advance);
  V1 — запасной путь advance с лимитом Ньютона 40 вместо 15 (без переключений);
  V2 — Ньютон с переключением набора фаз на итерациях, поячеечное ограничение
       (|dp| <= 0.3 p, |dSg| <= 0.2), линейный поиск по ||F||_2, лимит 40;
  V3 — V2 + замораживание ячейки «выше по потоку» на гранях с итерации K
       до сходимости, затем доводка без замораживания.
Печать: достигнутое время, принятые/отвергнутые шаги, размер шагов, время счёта.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\ladder_variants.py 20 10 B V3 24 300
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
from radial_blackoil.units import BAR_TO_PA as PBAR  # noqa: E402

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod, mode, variant = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
t_end_h, wall_cap = float(sys.argv[5]), float(sys.argv[6])
K_FREEZE = int(sys.argv[7]) if len(sys.argv) > 7 else 4
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
if mode == "A":
    model.set_bhp_control(p_ext / BAR_TO_PA)
else:
    model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA)

# ── Замораживание ячейки «выше по потоку» (копия face_component_fluxes_sm3s, blackoil.py:156-169) ──
frozen_left = None


def fluxes_frozen(state):
    self = model
    p, rs, sg = state.pressure_bar, state.rs_sm3_sm3, state.sg
    qow, qgfw, qgcw = self._well_fluxes(state)
    dp = p[:-1] - p[1:]
    left = dp >= 0 if frozen_left is None else frozen_left
    p_up = np.where(left, p[:-1], p[1:])
    rs_up = np.where(left, rs[:-1], rs[1:])
    sg_up = np.where(left, sg[:-1], sg[1:])
    lo, lg = self._phase_mobilities_surface(p_up, rs_up, sg_up)
    T = self.grid.internal_transmissibility_m3
    qoi = T * lo * dp * PBAR
    qgfi = T * lg * dp * PBAR
    qgci = rs_up * qoi + qgfi
    dpo = p[-1] - self.p_outer_bar
    p_u, rs_u, sg_u = (p[-1], rs[-1], sg[-1]) if dpo >= 0 else (self.p_outer_bar, self.outer_rs, 0.0)
    lo, lg = self._phase_mobilities_surface(p_u, rs_u, sg_u)
    To = self.grid.outer_transmissibility_m3
    qoo = float(To * lo * dpo * PBAR)
    qgfo = float(To * lg * dpo * PBAR)
    qgco = float(rs_u * qoo + qgfo)
    return {'oil_well': qow, 'free_gas_well': qgfw, 'gas_component_well': qgcw, 'oil_internal': qoi,
            'free_gas_internal': qgfi, 'gas_component_internal': qgci, 'oil_outer': qoo,
            'free_gas_outer': qgfo, 'gas_component_outer': qgco}


if variant == "V3":
    model.face_component_fluxes_sm3s = fluxes_frozen


def switch_phases(pn, xn, mask):
    """Переключение набора фаз в точке (pn, xn): S_g < 0 -> R_s по отношению газ/нефть; R_s > R_s^sat -> S_g «закрытого сосуда»."""
    pvt = model.pvt
    rs_sat = pvt.rs_sat(pn)
    deact = mask & (xn < -model.sg_switch_tol)
    act = (~mask) & (xn > rs_sat + model.rs_switch_tol)
    xn = xn.copy()
    if np.any(deact):
        sg = xn[deact]
        bo = pvt.bo(pn[deact], rs_sat[deact])
        bg = pvt.bg(pn[deact])
        xn[deact] = np.maximum(rs_sat[deact] + sg * bo / ((1.0 - sg) * bg), 0.0)
    if np.any(act):
        rsat = rs_sat[act]
        bo = pvt.bo(pn[act], rsat)
        bg = pvt.bg(pn[act])
        d = np.maximum(xn[act] - rsat, 0.0)
        sg0 = np.maximum(d * bg / (bo + d * bg), 1e-8)
        if model.sg_activation_cap is not None:
            sg0 = np.minimum(sg0, model.sg_activation_cap)
        xn[act] = sg0
    m = mask.copy()
    m[deact] = False
    m[act] = True
    return xn, m, int(deact.sum() + act.sum())


def newton_switching(state_old, dt, freeze=False, max_iter=MAX_IT, rtol=1e-8, atol=1e-11):
    """Ньютон с переключением набора фаз на итерациях, поячеечным ограничением и поиском по ||F||_2."""
    global frozen_left
    mask = state_old.gas_active.copy()
    z = model.pack(state_old, mask)
    scale = max(np.linalg.norm(model.residual(z, state_old, dt, mask), np.inf), 1e-9)
    tol = atol + rtol * scale
    switched = 0
    total_sw = 0
    frozen_left = None
    try:
        for it in range(1, max_iter + 1):
            if freeze and frozen_left is None and it > K_FREEZE:
                p = z[:n]
                frozen_left = (p[:-1] - p[1:]) >= 0
            J, f = model.finite_difference_jacobian(z, state_old, dt, mask)
            nrm = np.linalg.norm(f, np.inf)
            if nrm <= tol and switched == 0:
                if frozen_left is not None:
                    # доводка без замораживания: направление «выше по потоку» по решению
                    p = z[:n]
                    if np.array_equal(frozen_left, (p[:-1] - p[1:]) >= 0):
                        frozen_left = None
                        f = model.residual(z, state_old, dt, mask)
                        if np.linalg.norm(f, np.inf) <= tol:
                            break
                    frozen_left = None
                    freeze = False
                    continue
                break
            try:
                dz = model._linear_solve(J, -f)
            except Exception:
                return model.unpack(z, mask), BlackOilNewtonReport(False, it, float(nrm))
            p, x = z[:n], z[n:]
            lim = DP_REL * np.maximum(p, 1.0)
            dp = np.clip(dz[:n], -lim, lim)
            dx = np.where(mask, np.clip(dz[n:], -DS_MAX, DS_MAX), dz[n:])
            mf = np.linalg.norm(f)
            alpha = 1.0
            acc = False
            for _ in range(10):
                pn = np.maximum(p + alpha * dp, 1.0 + 1e-6)
                xn = x + alpha * dx
                xn = np.where(mask, xn, np.maximum(xn, 0.0))
                trial = np.concatenate([pn, xn])
                if np.all(np.isfinite(trial)) and np.linalg.norm(model.residual(trial, state_old, dt, mask)) < mf:
                    acc = True
                    break
                alpha *= 0.5
            if not acc:
                return model.unpack(z, mask), BlackOilNewtonReport(False, it, float(nrm))
            xn, mask, switched = switch_phases(pn, xn, mask)
            total_sw += switched
            z = np.concatenate([pn, xn])
        else:
            f = model.residual(z, state_old, dt, mask)
            return model.unpack(z, mask), BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)))
    finally:
        frozen_left = None
    new = model.unpack(z, mask)
    new.sg[mask & (new.sg < 0)] = 0.0
    return new, BlackOilNewtonReport(True, it - 1, float(nrm), phase_switches=total_sw)


def stage4(state_old, dt):
    if variant == "V1":
        model._sg_lower_bound = None
        try:
            return model._fallback(state_old, dt, 12, 40)
        finally:
            model._sg_lower_bound = -0.05
    if model.control_mode == "BHP":
        target = float(model.p_bhp_bar)
        shut = float(state_old.pressure_bar[0]) <= target
        model._well_branch = "shut" if shut else "open"
    try:
        new, rep = newton_switching(state_old, dt, freeze=(variant == "V3"))
    finally:
        model._well_branch = None
    if rep.converged and model.control_mode == "BHP":
        p0 = float(new.pressure_bar[0])
        if (p0 > target) if shut else (p0 < target):
            rep.converged = False
    return new, rep


print(f"=== {BASES[base_key]}: останов, режим {mode}, вариант {variant}, после {n_prod} сут; "
      f"до {t_end_h} ч, предел счёта {wall_cap:.0f} с ===")
ps, t, dt = ps0, 0.0, 60.0
n_acc = n_rej = n4 = 0
steps = []
t1 = time.perf_counter()
while t < t_end_h * 3600.0 - 1e-6 and time.perf_counter() - t1 < wall_cap:
    step = min(dt, t_end_h * 3600.0 - t)
    new, rep = model.advance(ps, step)
    how = "штатно"
    if not rep.converged and variant != "V0":
        new, rep = stage4(ps, step)
        how = "ступень 4"
    if rep.converged:
        ps, t = new, t + step
        n_acc += 1
        n4 += how == "ступень 4"
        steps.append(step)
        dt = min(step * 2.0, DAY)
    else:
        n_rej += 1
        dt = step / 2.0
        if dt < 1e-3:
            break
el = time.perf_counter() - t1
st = np.array(steps) if steps else np.zeros(1)
print(f"итог: t = {t/3600:.3f} ч ({t/DAY:.3f} сут) за {el:.0f} с; принято {n_acc} (ступенью 4 — {n4}), "
      f"отказов {n_rej}; шаг: медиана {np.median(st):.0f} с, максимум {st.max():.0f} с, последний {st[-1]:.0f} с; "
      f"p0 = {ps.pressure_bar[0]:.2f} бар, 2ф = {int(ps.gas_active.sum())}, max Sg = {ps.sg.max():.4f}")
