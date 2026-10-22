"""FEAT-029: числа плана на черновом конфиге примера 17 (draft_17/config.json).

Расчёт тем же путём, что фикстура results (load_config → SimulatorFactory →
run). Печать: время и дробление шага; таблица записей у забоя; профили на
характерных записях; балансы энергии (по области и по зонам r < r_k, члены
по ячейкам — как в local_budget.py) и массы; проверка R_s; диапазоны
рисунков PVT и ОФП. История — в plan_numbers_<каталог конфига>.npz.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-029\\probes\\plan_numbers.py
Переменная FEAT029_CONFIG — другой конфиг (например, папка примера после реализации).
"""

import contextlib
import io
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path(os.environ.get("FEAT029_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory, _create_pvt  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationHistory  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator as Acc  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
from mass_balance import compute_mass_balance  # noqa: E402
from rs_analytics import report_rs  # noqa: E402
from pvt_plot import report_pvt  # noqa: E402
from relperm_plot import _sg_range  # noqa: E402

DAY = 86400.0
CFG = Path(os.environ.get("FEAT029_CONFIG", HERE / "draft_17" / "config.json"))
cfg = load_config(CFG)
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
grid = sim._grid
V, N, r = grid.volumes, grid.N, grid.r_centers
pvt = _create_pvt(cfg)
T0, p0, Rs0 = cfg.initial_conditions.T0, cfg.initial_conditions.p0, cfg.initial_conditions.Rs0
pb0 = float(pvt.pb(np.array([Rs0]))[0])

# ── Счётчик вызовов энергии: дробление шага A-retry ──
dt_calls = []
_inner = sim._energy


class _Count:
    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        dt_calls.append(dt)
        return _inner.solve(hydro_result, state_prev, dt, bc, collect)


sim._energy = _Count()

# ── Члены баланса энергии по ячейкам (как local_budget.py) ──
KEYS = ("dE", "adiab", "deg", "jt", "conv")
cum = {k: np.zeros(N) for k in KEYS}
snaps = []
_add_sub, _add_acc = Acc.add_substep, Acc.add_accumulation


def add_substep(self, hydro_result, state_prev, dt, props, Phi_o, Phi_g,
                Q_T_ext, J_jt, Q_ad, Q_deg, T_ext):
    cum["jt"] += J_jt * dt
    cum["adiab"] += V * Q_ad * dt
    cum["deg"] += V * Q_deg * dt
    self._f29 = (np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0),
                 np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0), dt, T_ext)
    return _add_sub(self, hydro_result, state_prev, dt, props, Phi_o, Phi_g,
                    Q_T_ext, J_jt, Q_ad, Q_deg, T_ext)


def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
    Pp, Pm, dts, T_ext = self._f29
    T_left = np.concatenate(([T_new[0]], T_new[:-1]))
    T_right = np.concatenate((T_new[1:], [T_ext]))
    F = Pp[0:N] * (T_new - T_left) + Pm[1:N + 1] * (T_right - T_new)
    cum["conv"] += -F * dts
    cum["dE"] += rho_cp_eff * V * (T_new - T_prev)
    return _add_acc(self, T_new, T_prev, rho_cp_eff, dt)


Acc.add_substep, Acc.add_accumulation = add_substep, add_accumulation
_append = SimulationHistory.append


def append(self, *a, **kw):
    snaps.append({k: v.copy() for k, v in cum.items()})
    return _append(self, *a, **kw)


SimulationHistory.append = append

t_wall = time.perf_counter()
h = sim.run(init)
wall = time.perf_counter() - t_wall
S = h.states
n_rec = len(S)
# Конец добычи — последняя запись под управлением по давлению
E = max(i for i, iv in enumerate(cfg.time.history) if iv.control == "pressure") + 1
dts = np.array(dt_calls)
n_steps_sched = int(round(sum(iv.dt for iv in cfg.time.history) / cfg.time.dt_integration))
print(f"=== {CFG}: N = {N}, записей {n_rec}, конец добычи — запись {E} ===")
print(f"счёт {wall:.0f} с; вызовов энергии {len(dts)} при {n_steps_sched} шагах расписания; "
      f"dt: min {dts.min():.3f} с, max {dts.max():.0f} с; вызовов с dt < 3600: {int(np.sum(dts < 3599.0))}")
print(f"p_b(R_s0) = {pb0/1e6:.4f} МПа; R_s,eq(p0) = {float(pvt.Rs_eq(np.array([p0]))[0]):.3f}")

# ── Таблица записей у забоя ──
q_o = np.array([w.q_o_std for w in h.well_data])
q_g = np.array([w.q_g_std for w in h.well_data])
pwf = np.array([w.p_wf for w in h.well_data])
pw = np.array([s.p[0] for s in S])
Tw = np.array([s.T[0] for s in S])
print(f"{'зап':>4} {'t, сут':>8} {'q_o, м3ст/с':>12} {'q_g, м3ст/с':>12} {'GOR':>8} {'p_wf':>9} {'p(r_w)':>9} "
      f"{'T(r_w)':>9} {'ΔT':>8} {'Sg_w':>7} {'Rs_w':>7} {'Sg>0':>5} {'2ф':>4}")
for n in range(n_rec):
    s = S[n]
    gor = q_g[n] / q_o[n] if q_o[n] > 0 else 0.0
    print(f"{n:>4} {h.times[n]/DAY:>8.4f} {q_o[n]:>12.5e} {q_g[n]:>12.5e} {gor:>8.2f} {pwf[n]/1e6:>9.4f} "
          f"{pw[n]/1e6:>9.4f} {Tw[n]:>9.4f} {Tw[n]-T0:>8.3f} {s.Sg[0]:>7.4f} {s.Rs[0]:>7.3f} "
          f"{int(np.count_nonzero(s.Sg > 0)):>5} {int(np.count_nonzero(s.regime == 1)):>4}")

sh = range(E, n_rec)
print(f"останов: p(r_w) не убывает: {bool(np.all(np.diff(pw[E:]) >= 0))}; "
      f"T(r_w) возрастает строго: {bool(np.all(np.diff(Tw[E:]) > 0))}; "
      f"max|p_wf - p[0]| на останове = {max(abs(pwf[n] - pw[n]) for n in range(E + 1, n_rec)):.3e} Па; "
      f"q_o, q_g на останове ровно 0: {bool(np.all(q_o[E+1:] == 0) and np.all(q_g[E+1:] == 0))}")
above = [n for n in sh if pw[n] > pb0]
print(f"первая запись с p(r_w) > p_b: {above[0] if above else None}; "
      f"первая запись без газа в ячейке 0: {next((n for n in sh if S[n].Sg[0] == 0), None)}; "
      f"max|p - p0| на финале = {np.max(np.abs(S[-1].p - p0)):.3e} Па")

# ── Профили ──
radii = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 199.0]
idx = [int(np.argmin(np.abs(r - x))) for x in radii]
print("радиусы:", " ".join(f"{r[i]:.2f}" for i in idx))
for n in sorted({E, E + 1, E + 12, E + 24, n_rec - 1, min(E + 29, n_rec - 1)}):
    s = S[n]
    dT = s.T - T0
    gas = np.nonzero(s.Sg > 0)[0]
    gz = f"{r[gas[0]]:.2f}…{r[gas[-1]]:.2f} м ({len(gas)})" if len(gas) else "нет"
    cold = np.nonzero(dT < -0.1 * abs(dT[0]))[0] if dT[0] < 0 else []
    print(f"--- запись {n} ({h.times[n]/DAY:.3f} сут): газ {gz}; ΔT < −0.1|ΔT_w| до r = "
          f"{(r[cold[-1]] if len(cold) else 0):.2f} м; max ΔT = {dT.max():+.4f} при r = {r[np.argmax(dT)]:.2f}; "
          f"R_s max {s.Rs.max():.3f} при r = {r[np.argmax(s.Rs)]:.2f}")
    print("  ΔT  " + " ".join(f"{dT[i]:>8.3f}" for i in idx))
    print("  S_g " + " ".join(f"{s.Sg[i]:>8.4f}" for i in idx))
    print("  p   " + " ".join(f"{s.p[i]/1e6:>8.3f}" for i in idx))
    print("  R_s " + " ".join(f"{s.Rs[i]:>8.2f}" for i in idx))

# ── Баланс энергии по области ──
bal = compute_balance(h, grid, cfg)
ck = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")
print(f"баланс энергии: отн. невязка на финале {bal['rel_residual'][-1]:.2e}, max по записям "
      f"{np.max(bal['rel_residual']):.2e}")
for lab, a, b in (("добыча", 0, E), ("первые сутки останова", E, E + 24), ("весь останов", E, n_rec - 1),
                  ("весь расчёт", 0, n_rec - 1)):
    print(f"  {lab:>22}: " + ", ".join(f"{k} {bal[k][b]-bal[k][a]:+.3e}" for k in ck))

# ── Баланс энергии по зонам ──
def seg(a, b):
    d = {k: snaps[b][k] - snaps[a][k] for k in KEYS}
    d["cond"] = d["dE"] - d["adiab"] - d["deg"] - d["jt"] - d["conv"]
    return d


segs = [(E, E + 1, "1-й час"), (E + 1, E + 24, "2–24 ч"), (E + 24, n_rec - 1, "сутки 2–15"),
        (E, n_rec - 1, "весь останов")]
for rk in (0.3, 1.0, 3.0, 10.0, 30.0, 300.0):
    m = r < rk
    print(f"зона r < {rk:g} м ({int(m.sum())} яч.), Дж:")
    for a, b, lab in segs:
        d = seg(a, b)
        tot = float(np.sum(d["dE"][m]))
        parts = ", ".join(f"{k} {float(np.sum(d[k][m])):+.2e} ({float(np.sum(d[k][m]))/tot*100:+.0f} %)"
                          for k in ("adiab", "deg", "conv", "jt", "cond"))
        print(f"  {lab:>13}: dE {tot:+.2e}; {parts}")

# ── Баланс массы ──
mb = compute_mass_balance(h)
for a, nm in (("o", "нефть"), ("g", "газ")):
    print(f"масса, {nm}: ΔM {mb[f'dM_{a}'][-1]:+.4e}, добыча {mb[f'prod_{a}'][-1]:.4e}, приток "
          f"{mb[f'inflow_{a}'][-1]:.4e}, отн. невязка max {np.max(mb[f'rel_residual_{a}']):.2e}; "
          f"ΔM на конце добычи {mb[f'dM_{a}'][E]:+.4e}")

# ── Проверка R_s и рабочие диапазоны рисунков ──
with contextlib.redirect_stdout(io.StringIO()) as buf:
    rep = report_rs(cfg, h, pvt)
    prep = report_pvt(cfg, h)
print("report_rs:", {k: (float(v) if not isinstance(v, int) else v) for k, v in rep.items()})
print("report_pvt:", {k: v for k, v in prep.items() if k in ("pb", "p_lo", "p_hi", "two_phase",
                                                            "nodes_in_range", "Rs_lo", "Rs_hi")})
print("S_g по всей истории:", _sg_range(h))
# Имя — по каталогу конфига: прогоны разных конфигов не затирают друг друга
np.savez_compressed(HERE / f"plan_numbers_{CFG.parent.name}.npz", t=np.array(h.times), r=r,
                    p=np.array([s.p for s in S]), T=np.array([s.T for s in S]),
                    Sg=np.array([s.Sg for s in S]), Rs=np.array([s.Rs for s in S]),
                    q_o=q_o, q_g=q_g, pwf=pwf)
