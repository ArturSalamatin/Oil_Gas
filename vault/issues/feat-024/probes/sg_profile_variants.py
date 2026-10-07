"""FEAT-024: откуда изломы профиля S_g примера 14 — узлы таблиц или решатель.

Проверки на 360 сут:
  1. замыкание при GOR = 146.36 (фактический GOR потока) при численном p —
     если совпадает с численным S_g, форма внутренней зоны задана таблицами;
  2. ОФП Кори n_g = 3 таблицей с шагом 0.01 вместо 0.05 (узел 0.20 сглажен);
  3. сетка N = 150 вместо 50 (разрешение зоны накопления у фронта).
График — sg_profile_variants.png рядом со скриптом.

Запуск (из numerical_solver рабочего дерева .worktrees/feat-024):
    python <этот файл>
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path("HydroSolverPrototype/Prototype_1.0.3").resolve()))
sys.path.insert(0, str(Path("examples").resolve()))
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from closed_form import Closure  # noqa: E402
from gpn_multiphase_solver.factory import (  # noqa: E402
    SimulatorFactory, _create_pvt, _create_relperm)
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EX = Path("examples/14_high_gor_cooling")
WORK = HERE / "sgdiag"
WORK.mkdir(exist_ok=True)


def run(cfg, label):
    t0 = time.perf_counter()
    sim, init = SimulatorFactory.from_config(cfg)
    h = sim.run(init)
    wd = h.well_data[-1]
    print(f"{label}: {time.perf_counter() - t0:.1f} с, GOR = {wd.q_g_std / wd.q_o_std:.3f}")
    return sim._grid.r_centers, h.states[-1]


# ── База ──
base = load_config(EX / "config.json")
r0, st0 = run(base, "база N=50, ОФП шаг 0.05")
gor_base = 146.360

# ── 1. Замыкание при GOR потока и при R_s0 ──
pvt, rp = _create_pvt(base), _create_relperm(base)


def closure_sg(p, gor):
    clo = Closure(pvt, rp, gor)
    return np.array([clo.Sg(pp) for pp in p])


sg146 = closure_sg(st0.p, gor_base)
inner = r0 < 40.0
print(f"|S_g - замыкание(GOR=146.36)| при r < 40 м: max {np.abs(st0.Sg - sg146)[inner].max():.2e}")

# ── 2. ОФП с шагом 0.01 ──
S = np.round(np.arange(0.0, 0.8 + 1e-9, 0.01), 2)
kro = np.interp(S, [0.0, 0.1, 0.2, 0.4, 0.6, 0.8], [1.0, 0.8, 0.6, 0.3, 0.1, 0.0])
krg = 0.8 * np.clip((S - 0.1) / 0.7, 0.0, 1.0) ** 3
fine_dir = WORK / "relperm_001"
fine_dir.mkdir(exist_ok=True)
for f in ("oil_pvt.csv", "gas_pvt.csv"):
    (fine_dir / f).write_bytes((EX / f).read_bytes())
with open(fine_dir / "relperm.csv", "w", encoding="utf-8", newline="\n") as fh:
    fh.write("Sg,kro,krg\n")
    for s, a, b in zip(S, kro, krg):
        fh.write(f"{s:.2f},{a:.6g},{b:.6g}\n")
(fine_dir / "config.json").write_bytes((EX / "config.json").read_bytes())
r1, st1 = run(load_config(fine_dir / "config.json"), "ОФП шаг 0.01")

# ── 3. Сетка N = 150 ──
# Суточный первый шаг на N = 150 не сходится (512 подшагов по 169 с) —
# первые сутки разгоном: 1, 1, 2, 4, 8, 8 ч; затем 29 сут и 11 × 30 сут.
# N = 150 не сходится и так: часовой первый шаг при max_retries = 9
# (512 × 7.03 с) и при 12 (4096 × 0.88 с). Пробуем N = 100 — по очереди,
# без остановки на отказе.
from gpn_multiphase_solver.io.config import HistoryInterval  # noqa: E402
ramp = [3600.0, 3600.0, 7200.0, 14400.0, 28800.0, 28800.0, 29 * 86400.0] + [30 * 86400.0] * 11
r2 = st2 = None
N_fine = int(sys.argv[1]) if len(sys.argv) > 1 else 100
for label, hist in (("сутки", None), ("разгон шага", ramp)):
    c = copy.deepcopy(base)
    c.grid.N = N_fine
    if hist:
        c.time.history = [HistoryInterval(dt=d, control="pressure", p_wf=6.0e6) for d in hist]
    try:
        r2, st2 = run(c, f"сетка N={N_fine} ({label})")
        break
    except RuntimeError as e:
        print(f"сетка N={N_fine} ({label}): отказ — {str(e)[:80]}")

# ── Таблица в опорных точках ──
print(f"\n{'r, м':>7} {'N50':>8} {'зам146':>8} {'зам150':>8} {'ОФП.01':>8} {'N' + str(N_fine):>8}")
sg150 = closure_sg(st0.p, 150.0)
for rr in (0.11, 0.5, 0.8, 1.0, 1.3, 2.0, 10.0, 30.0, 40.0, 50.0, 64.0, 80.0, 100.0, 115.0):
    fine = f"{np.interp(rr, r2, st2.Sg):8.4f}" if st2 is not None else "       —"
    print(f"{rr:7.2f} {np.interp(rr, r0, st0.Sg):8.4f} {np.interp(rr, r0, sg146):8.4f} "
          f"{np.interp(rr, r0, sg150):8.4f} {np.interp(rr, r1, st1.Sg):8.4f} {fine}")

# ── Где лежат узлы таблиц ──
j_rp = np.where(np.diff(np.sign(st0.Sg - 0.2)))[0]
j_gas = np.where(np.diff(np.sign(st0.p - 15e6)))[0]
print(f"\nузел ОФП S_g = 0.20: между r = {r0[j_rp[0]]:.3f} и {r0[j_rp[0] + 1]:.3f} м")
print(f"узел газовой таблицы p = 15 МПа: между r = {r0[j_gas[0]]:.3f} и {r0[j_gas[0] + 1]:.3f} м")

# ── График ──
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(r0, st0.Sg, "o-", ms=3, label="расчёт: N = 50, ОФП шаг 0.05 (пример 14)")
if st2 is not None:
    ax.plot(r2, st2.Sg, "-", lw=1, label=f"расчёт: N = {N_fine}")
ax.plot(r1, st1.Sg, "-", lw=1, label="расчёт: ОФП шаг 0.01")
ax.plot(r0, sg146, "k--", lw=1, label="замыкание при численном p, GOR = 146.36")
ax.plot(r0, sg150, "k:", lw=1, label="замыкание при численном p, GOR = R_s0 = 150")
ax.axvspan(r0[j_rp[0]], r0[j_gas[0] + 1], color="0.9", zorder=0,
           label="между узлами S_g = 0.20 (ОФП) и p = 15 МПа (газ)")
ax.set_xscale("log")
ax.set_xlabel("r, м")
ax.set_ylabel("S_g")
ax.set_title("Пример 14, 360 сут: профиль S_g — варианты и замыкание")
ax.grid(alpha=0.3)
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(HERE / "sg_profile_variants.png", dpi=110)
print("график:", HERE / "sg_profile_variants.png")
