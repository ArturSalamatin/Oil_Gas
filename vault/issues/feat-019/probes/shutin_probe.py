"""FEAT-019: замер останова скважины — добыча, затем останов (до реализации).

Конфиг-заготовка — пример 12 (табличные PVT/ОФП, R_s0 = 30, p0 = 15.5 МПа,
p_b = 15 МПа) или 20 (Standing/Кори, R_s0 = 300, p0 = 33 МПа, p_b = 30.29 МПа).
Меняется только time.history: n_prod суток добычи при p_wf примера, затем
n_shut суток останова. Способ останова:
  A — управление по давлению, p_wf = p_ext (закрытие по eq:bc_pwf_shutin);
  B — управление по дебиту, q_oil = 0, min_bhp = 1 атм (eq:bc_rate_well).

Что замеряется:
  - время sim.run, принятые подшаги, дробление (dt < dt_integration);
  - подшаги останова с G_o[0] != 0 и G_g[0] != 0 (должно быть 0);
  - таблица по записям: p(r_w), T(r_w), S_g(r_w), max S_g, двухфазные ячейки,
    свободный газ при p > p_b, R_s мин/макс, недонасыщенная нефть;
  - баланс массы компонентов (запас + интеграл потоков по подшагам);
  - баланс энергии; report_rs на финале.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-019\\probes\\shutin_probe.py 12 A 15 15
"""

import copy
import sys
import time
from collections import Counter
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
from energy_balance import compute_balance  # noqa: E402
from rs_analytics import report_rs  # noqa: E402

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}

base_key, variant = sys.argv[1], sys.argv[2]
n_prod, n_shut = int(sys.argv[3]), int(sys.argv[4])
dt_hist = float(sys.argv[5]) if len(sys.argv) > 5 else DAY
# Необязательно: dt_integration (с) и max_retries — замер зависимости отказа от шага
dt_int_arg = float(sys.argv[6]) if len(sys.argv) > 6 else None
retries_arg = int(sys.argv[7]) if len(sys.argv) > 7 else None
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"


class Recording:
    """Обёртка EnergySolver.solve: пишет каждый ПРИНЯТЫЙ подшаг, физику не трогает."""

    def __init__(self, inner):
        self._inner, self.rows = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        st = hr.state
        self.rows.append(dict(
            t=st.t, dt=dt, G_o0=float(hr.G_o[0]), G_g0=float(hr.G_g[0]),
            G_oN=float(hr.G_o[-1]), G_gN=float(hr.G_g[-1]),
            p0=float(st.p[0]), p_wf_eff=float(hr.p_wf),
            shut=not hasattr(bc.well, "p_wf") or bc.well.p_wf >= bc.p_ext))
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def make_cfg():
    cfg = load_config(BASE)
    cfg.output.log_level = "ERROR"
    iv = cfg.time.history[0]
    p_ext = cfg.initial_conditions.p0
    hist = []
    n_per_day = int(round(DAY / dt_hist))
    for k in range(n_prod * n_per_day):
        x = copy.deepcopy(iv)
        x.dt = dt_hist
        hist.append(x)
    for k in range(n_shut * n_per_day):
        x = copy.deepcopy(iv)
        x.dt = dt_hist
        if variant == "A":
            x.control, x.p_wf = "pressure", p_ext
        else:
            x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    if dt_int_arg is not None:
        cfg.time.dt_integration = dt_int_arg
    if retries_arg is not None:
        cfg.numerics.max_retries = retries_arg
    return cfg


cfg = make_cfg()
sim, init = SimulatorFactory.from_config(cfg)
rec = Recording(sim._energy)
sim._energy = rec
t0 = time.perf_counter()
h = sim.run(init)
el = time.perf_counter() - t0

grid, pvt = sim._grid, rec._inner._pvt
Rs0 = cfg.initial_conditions.Rs0
pb = float(pvt.pb(np.array([Rs0]))[0])
r = grid.r_centers
phiV = cfg.rock.porosity * grid.volumes
dt_int = cfg.time.dt_integration

print(f"=== база {BASES[base_key]}, останов {variant}: {n_prod} сут добычи + {n_shut} сут "
      f"останова, запись {dt_hist/3600:.1f} ч, dt_integration = {dt_int:.0f} с ===")
print(f"p0 = {cfg.initial_conditions.p0/1e6:.3f} МПа, p_b(R_s0) = {pb/1e6:.3f} МПа, N = {len(r)}")
print(f"sim.run {el:.1f} с; записей {len(h.states)}; принятых подшагов {len(rec.rows)}")
dts = Counter(round(x["dt"], 2) for x in rec.rows)
print(f"dt подшагов: {dict(sorted(dts.items()))}")
sub = Counter(int((x["t"] - 1e-6) // DAY) + 1 for x in rec.rows if x["dt"] < dt_int - 1e-9)
print(f"сутки с дроблением (сутки: мелких подшагов): {dict(sorted(sub.items()))}")

t_shut = n_prod * DAY
sh = [x for x in rec.rows if x["t"] > t_shut + 1e-6]
pr = [x for x in rec.rows if x["t"] <= t_shut + 1e-6]
print(f"подшаги останова: {len(sh)}; max|G_o[0]| = {max(abs(x['G_o0']) for x in sh):.3e}, "
      f"max|G_g[0]| = {max(abs(x['G_g0']) for x in sh):.3e} м³ст/с")
print(f"подшаги добычи с G_o[0] = 0 (закрыта): {sum(1 for x in pr if x['G_o0'] == 0.0)}; "
      f"с G_o[0] > 0 (закачка): {sum(1 for x in rec.rows if x['G_o0'] > 0.0)}")
print(f"p_wf факт. на останове: первые 3 = "
      f"{[round(x['p_wf_eff']/1e6, 4) for x in sh[:3]]}, p[0] = {[round(x['p0']/1e6, 4) for x in sh[:3]]}")


def masses(st):
    """Запас компонентов в пласте, м³ст: нефть и весь газ (растворённый + свободный)."""
    Bo, Bg = pvt.Bo(st.p, st.Rs), pvt.Bg(st.p)
    So = 1.0 - st.Sg
    oil = np.sum(phiV * So / Bo)
    gas = np.sum(phiV * (So * st.Rs / Bo + st.Sg / Bg))
    return oil, gas


# Баланс массы: dM/dt = G[0] - G[N] (G > 0 — от скважины; G[0] < 0 — отбор,
# G[N] < 0 — приток через контур)
mo0, mg0 = masses(h.states[0])
mo1, mg1 = masses(h.states[-1])
flow_o = sum(x["dt"] * (x["G_o0"] - x["G_oN"]) for x in rec.rows)
flow_g = sum(x["dt"] * (x["G_g0"] - x["G_gN"]) for x in rec.rows)
prod_o = -sum(x["dt"] * x["G_o0"] for x in rec.rows)
prod_g = -sum(x["dt"] * x["G_g0"] for x in rec.rows)
print(f"баланс массы нефти: ΔM = {mo1 - mo0:.4e}, ∫потоки = {flow_o:.4e}, "
      f"невязка/добыча = {(mo1 - mo0 - flow_o)/prod_o:.2e}")
print(f"баланс массы газа:  ΔM = {mg1 - mg0:.4e}, ∫потоки = {flow_g:.4e}, "
      f"невязка/добыча = {(mg1 - mg0 - flow_g)/prod_g:.2e}")
print(f"накопленная добыча: нефть {prod_o:.4e} м³ст, газ {prod_g:.4e} м³ст, "
      f"газ/нефть {prod_g/prod_o:.2f}; запас газ/нефть в начале {mg0/mo0:.3f}, в конце {mg1/mo1:.3f}")

print(f"\n{'сут':>5} | {'p_wf':>7} | {'q_o':>10} | {'p[0]':>7} {'T_w':>8} {'S_g(r_w)':>8} "
      f"{'maxS_g':>7} | {'n_2ф':>4} {'r_2ф,max':>8} | {'Sg>0,p>pb':>9} | {'Rs мин':>7} {'Rs макс':>7} | {'недонас':>7}")
step = max(1, int(round(DAY / dt_hist)))
for n, st in enumerate(h.states):
    if n % step and n != len(h.states) - 1:
        continue
    w = h.well_data[n]
    tp = np.nonzero(st.regime == 1)[0]
    free_hi = int(np.count_nonzero((st.Sg > 0) & (st.p > pb)))
    und = int(np.count_nonzero((st.regime == 2) & (st.Rs < Rs0 - 1e-9)))
    print(f"{h.times[n]/DAY:5.1f} | {w.p_wf/1e6:7.3f} | {w.q_o_std:10.3e} | {st.p[0]/1e6:7.3f} "
          f"{st.T[0]:8.3f} {st.Sg[0]:8.4f} {st.Sg.max():7.4f} | {tp.size:4d} "
          f"{(r[tp[-1]] if tp.size else 0):8.2f} | {free_hi:9d} | {st.Rs.min():7.2f} {st.Rs.max():7.2f} | {und:7d}")

# Финальный профиль у забоя
st = h.states[-1]
Rs_sat = pvt.Rs_eq(st.p)
print(f"\nфинал ({h.times[-1]/DAY:.1f} сут): j | r | p МПа | S_g | R_s | R_s,нас(p) | режим | T")
for j in list(range(0, 12)) + [15, 20, 30, 40, len(r) - 1]:
    if j < len(r):
        print(f"   {j:3d} {r[j]:8.3f} {st.p[j]/1e6:8.4f} {st.Sg[j]:8.5f} {st.Rs[j]:8.3f} "
              f"{Rs_sat[j]:8.3f} {st.regime[j]} {st.T[j]:8.3f}")

# T(r_w) на добыче и останове
tw = np.array([s.T[0] for s in h.states])
tt = np.array(h.times) / DAY
k_shut = int(np.searchsorted(tt, n_prod - 1e-9))
print(f"\nT(r_w): начало {tw[0]:.3f}, конец добычи {tw[k_shut]:.3f}, финал {tw[-1]:.3f}; "
      f"на останове min {tw[k_shut:].min():.3f}, max {tw[k_shut:].max():.3f}")
pw = np.array([s.p[0] for s in h.states])
cross = np.nonzero((tt > n_prod) & (pw > pb))[0]
print(f"p(r_w) выше p_b на останове с {tt[cross[0]]:.2f} сут" if cross.size
      else "p(r_w) на останове выше p_b не поднялось")

bal = compute_balance(h, grid, cfg)
print(f"баланс энергии: rel_residual = {float(bal['rel_residual'][-1]):.2e}; "
      f"max по записям {float(np.max(np.abs(bal['rel_residual']))):.2e}")
print("\n── report_rs на финале ──")
report_rs(cfg, h, pvt)
