"""FEAT-029: добыча n_prod сут по конфигу примера, затем останов n_shut сут (q_oil = 0).

Расписание как у примера 16: n_prod суточных интервалов при p_wf примера,
затем 24 часовых интервала останова и (n_shut - 1) суточных.
dt_integration = 3600 с (требование BUG-020). Печать по записям: время
счёта, p, T, S_g, R_s у забоя, число ячеек с газом; вклады баланса энергии
на останове (приращения от конца добычи). История — в npz рядом с выводом.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-029\\probes\\shutin_scenario.py 20 10 10 1500
Аргументы: конфиг (19 | 20 | 21), сут добычи, сут останова, предел счёта, с.
"""

import copy
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

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationHistory  # noqa: E402

DAY = 86400.0
HOUR = 3600.0
BASES = {"19": "19_rs150_cooling", "20": "20_rs300_cooling", "21": "21_rs100_cooling"}
key, n_prod, n_shut = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
wall = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
tag = sys.argv[5] if len(sys.argv) > 5 else ""
name = BASES[key]

cfg = load_config(SOLVER / "examples" / name / "config.json")
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
for k in range(24 + n_shut - 1):
    x = copy.deepcopy(iv)
    x.dt = HOUR if k < 24 else DAY
    x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
    hist.append(x)
cfg.time.history = hist
cfg.time.dt_integration = 3600.0
# FEAT029_N — число ячеек вместо конфига примера (замер цены сетки)
if os.environ.get("FEAT029_N"):
    cfg.grid.N = int(os.environ["FEAT029_N"])
sim, init = SimulatorFactory.from_config(cfg)
grid = sim._grid
pvt = sim._pvt

# Перехват записей истории: время счёта на каждой записи и сама история —
# чтобы при обрыве по пределу счёта напечатать то, что посчиталось.
H = {}
WALL = []
_orig_append = SimulationHistory.append
t_wall0 = time.perf_counter()


def _append(self, *a, **kw):
    H["h"] = self
    WALL.append(time.perf_counter() - t_wall0)
    return _orig_append(self, *a, **kw)


SimulationHistory.append = _append
_orig_adv = sim._advance


def _adv(*a, **kw):
    if time.perf_counter() - t_wall0 > wall:
        raise TimeoutError("предел времени счёта")
    return _orig_adv(*a, **kw)


sim._advance = _adv

pb0 = float(pvt.pb(np.array([cfg.initial_conditions.Rs0]))[0])
print(f"=== {name}: {n_prod} сут добычи + {n_shut} сут останова (q_oil = 0); "
      f"dt_integration = 3600 с; N = {cfg.grid.N}; p_b = {pb0/1e6:.2f} МПа; T0 = {cfg.initial_conditions.T0} К ===")
try:
    sim.run(init)
    status = "✓"
except (RuntimeError, TimeoutError) as e:
    status = f"✗ {str(e)[:160]}"
h = H["h"]
el = time.perf_counter() - t_wall0
n_rec = len(h.states)
print(f"итог: {status}; счёт {el:.0f} с; записей {n_rec} из {1 + len(hist)}")

E_PROD = n_prod  # запись конца добычи
r = grid.r_centers
print(f"{'зап':>4} {'t, сут':>8} {'счёт, с':>8} {'p_w, МПа':>9} {'T_w, К':>9} {'ΔT_w':>7} "
      f"{'Sg_w':>6} {'Rs_w':>7} {'с газом':>7} {'q_o, м3/сут':>11} {'T_min, К':>9} {'r(T_min)':>8}")
T0 = cfg.initial_conditions.T0
for n in range(n_rec):
    if n > E_PROD + 24 or n <= E_PROD or n - E_PROD in (1, 2, 3, 4, 6, 8, 12, 18, 24) or n == 0:
        st = h.states[n]
        q_o = h.well_data[n].q_o_std * DAY
        i_min = int(np.argmin(st.T))
        print(f"{n:>4} {h.times[n]/DAY:>8.3f} {WALL[n]:>8.0f} {st.p[0]/1e6:>9.3f} {st.T[0]:>9.3f} "
              f"{st.T[0]-T0:>7.2f} {st.Sg[0]:>6.3f} {st.Rs[0]:>7.2f} {int(np.count_nonzero(st.Sg > 0)):>7} "
              f"{q_o:>11.2f} {st.T[i_min]:>9.3f} {r[i_min]:>8.2f}")

# Вклады баланса энергии на останове: приращения накопленных членов от конца добычи
if n_rec > E_PROD + 1:
    keys = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")
    b0 = h.balance[E_PROD]
    print("баланс энергии на останове (приращения от конца добычи), Дж:")
    print(f"{'зап':>4} {'t, сут':>8} " + " ".join(f"{k:>11}" for k in keys) + f" {'невязка':>10}")
    for n in range(E_PROD + 1, n_rec):
        if n - E_PROD in (1, 2, 3, 6, 12, 24) or n > E_PROD + 24:
            d = {k: h.balance[n][k] - b0[k] for k in keys}
            res = d["delta_E"] - sum(d[k] for k in keys[1:])
            print(f"{n:>4} {h.times[n]/DAY:>8.3f} " + " ".join(f"{d[k]:>11.3e}" for k in keys)
                  + f" {res:>10.2e}")
    bp = h.balance[E_PROD]
    print("баланс энергии на добыче (от t = 0), Дж: "
          + ", ".join(f"{k} {bp[k]:.3e}" for k in keys))

out = HERE / f"shutin_{key}_{n_prod}p{n_shut}s{tag}.npz"
np.savez_compressed(
    out, t=np.array(h.times), wall=np.array(WALL[:n_rec]), r=r,
    p=np.array([s.p for s in h.states]), T=np.array([s.T for s in h.states]),
    Sg=np.array([s.Sg for s in h.states]), Rs=np.array([s.Rs for s in h.states]),
    q_o=np.array([w.q_o_std for w in h.well_data]), q_g=np.array([w.q_g_std for w in h.well_data]),
    **{k: np.array([b[k] for b in h.balance]) for k in h.balance[0]})
print(f"история: {out.name}")
