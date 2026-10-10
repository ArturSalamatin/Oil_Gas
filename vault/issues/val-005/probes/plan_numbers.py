"""Проба VAL-005: наш решатель на конфиге из INPUT_TEMPLATE.xlsx — метрики против IMEX T07 и прототипа.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\val-005\\probes\\plan_numbers.py <config.json> <вывод прототипа>
Метрики против IMEX — как у авторов прототипа: ячейка i ↔ ячейка i IMEX (i = 1…100), отметки
1–30 сут (отметки «+1 мин» после смены режима авторы из приёмки исключили); дебиты — относительные, %.
"""
import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()  # запускать из numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
REG = PROTO / "regression"
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(SOLVER / "examples"))
print("SOLVER =", SOLVER)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
from mass_balance import compute_mass_balance  # noqa: E402

DAY, BAR = 86400.0, 1e5
STABLE = [1.0, 2.0, 4.0, 5.0, 6.0, 14.0, 15.0, 16.0, 30.0]   # приёмочные отметки авторов, сут

cfg_path, proto_out = Path(sys.argv[1]), Path(sys.argv[2])
cfg = load_config(cfg_path)
t0 = time.perf_counter()
sim, init = SimulatorFactory.from_config(cfg)
hist = sim.run(init)
elapsed = time.perf_counter() - t0
print(f"конфиг {cfg_path}, dt_integration = {cfg.time.dt_integration:g} с, расчёт {elapsed:.1f} с, "
      f"записей {len(hist.times)}")

times_d = np.array(hist.times) / DAY


def rec(day):
    """Номер записи на отметке day (сут); допуск 1e-3 с."""
    i = int(np.argmin(np.abs(times_d - day)))
    assert abs(times_d[i] - day) * DAY < 1e-3, (day, times_d[i])
    return i


# ── IMEX T07 ──
imex = defaultdict(dict)
with open(REG / "reference_imex_normalized" / "T07_profiles.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        imex[(round(float(r["time_day"]), 6), r["variable"])][int(r["cell"])] = float(r["value"])
imex_rates = {round(float(r["time_day"]), 6): r for r in
              csv.DictReader(open(REG / "reference_imex_normalized" / "T07_rates.csv", newline="", encoding="utf-8"))}

# ── Прототип на той же книге ──
pp = defaultdict(list)
with open(proto_out / "profiles.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        pp[round(float(r["time_day"]), 9)].append(r)
pr = {round(float(r["time_day"]), 9): r for r in
      csv.DictReader(open(proto_out / "rates.csv", newline="", encoding="utf-8"))}


def ours(i):
    s, w = hist.states[i], hist.well_data[i]
    qo, qg = w.q_o_std * DAY, w.q_g_std * DAY
    return s.p / BAR, s.Sg, s.Rs, qo, qg, qg / qo, w.p_wf / BAR


def rel(a, b):
    return 100.0 * (a - b) / b


print("\n== Против IMEX T07, отметки 1–30 сут ==")
print(f"{'сут':>6} {'max|Δp|':>9} {'max|ΔSg|':>9} {'RMSE Sg':>9} {'max|ΔRs|':>9} {'Δq_o,%':>8} {'Δq_g,%':>8} {'ΔGOR,%':>8}")
agg = defaultdict(float)
for d in STABLE:
    p, sg, rs, qo, qg, gor, _ = ours(rec(d))
    k = round(d, 6)
    ip = np.array([imex[(k, "P_bar")][c] for c in range(1, 101)])
    isg = np.array([imex[(k, "Sg")][c] for c in range(1, 101)])
    irs = np.array([imex[(k, "Rs")][c] for c in range(1, 101)])
    ir = imex_rates[k]
    m = {"dp": np.max(np.abs(p - ip)), "dsg": np.max(np.abs(sg - isg)),
         "rmse": float(np.sqrt(np.mean((sg - isg) ** 2))), "drs": np.max(np.abs(rs - irs)),
         "qo": rel(qo, float(ir["qo"])), "qg": rel(qg, float(ir["qg"])), "gor": rel(gor, float(ir["GOR"]))}
    for key, v in m.items():
        agg[key] = max(agg[key], abs(v))
    print(f"{d:6g} {m['dp']:9.4f} {m['dsg']:9.5f} {m['rmse']:9.5f} {m['drs']:9.4f} {m['qo']:8.3f} {m['qg']:8.3f} {m['gor']:8.3f}")
print("максимум:", {k: round(v, 5) for k, v in agg.items()})
print("авторы (прототип vs IMEX, T07): dp 0.13741, dsg 0.00460, rmse 0.00227, drs 0.04454, "
      "qo 0.508, qg 2.522, gor 2.557")

print("\n== Против прототипа на той же книге, все отчётные отметки ==")
print(f"{'сут':>12} {'max|Δp|':>9} {'max|ΔSg|':>9} {'max|ΔRs|':>9} {'Δq_o,%':>8} {'Δq_g,%':>8} {'ΔGOR,%':>8} {'Δp_wf':>7}")
aggp, aggp_stable = defaultdict(float), defaultdict(float)
for key in sorted(pp):
    if key == 0.0:
        continue
    p, sg, rs, qo, qg, gor, pwf = ours(rec(key))
    rows = pp[key]
    ppb = np.array([float(r["pressure_bar"]) for r in rows])
    psg = np.array([float(r["Sg"]) for r in rows])
    prs = np.array([float(r["Rs"]) for r in rows])
    r = pr[key]
    m = {"dp": np.max(np.abs(p - ppb)), "dsg": np.max(np.abs(sg - psg)), "drs": np.max(np.abs(rs - prs)),
         "qo": rel(qo, float(r["oil_rate_sm3_day"])), "qg": rel(qg, float(r["gas_rate_sm3_day"])),
         "gor": rel(gor, float(r["GOR_sm3_sm3"])), "pwf": pwf - float(r["BHP_bar"])}
    for k2, v in m.items():
        aggp[k2] = max(aggp[k2], abs(v))
        if round(key, 6) in [round(x, 6) for x in STABLE]:
            aggp_stable[k2] = max(aggp_stable[k2], abs(v))
    print(f"{key:12.7g} {m['dp']:9.4f} {m['dsg']:9.5f} {m['drs']:9.4f} {m['qo']:8.3f} {m['qg']:8.3f} {m['gor']:8.3f} {m['pwf']:7.3f}")
print("максимум по всем:", {k: round(v, 5) for k, v in aggp.items()})
print("максимум на 1–30 сут:", {k: round(v, 5) for k, v in aggp_stable.items()})

# ── Балансы и температура ──
bal = compute_balance(hist, sim._grid, cfg)
mb = compute_mass_balance(hist)
print(f"\nбаланс энергии: |rel| на финале {abs(float(bal['rel_residual'][-1])):.2e}, "
      f"max {np.max(np.abs(bal['rel_residual'])):.2e}")
print(f"баланс массы: нефть {np.max(mb['rel_residual_o']):.2e}, газ {np.max(mb['rel_residual_g']):.2e}")
print("\nВсе записи: t, p_wf, q_o, q_g (м³ст/сут), GOR, T(r_w) - T0, S_g(r_w), ячеек с газом, газ до r")
T0 = cfg.initial_conditions.T0
for n, t in enumerate(times_d):
    s, w = hist.states[n], hist.well_data[n]
    two = np.nonzero(s.Sg > 0)[0]
    gor = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
    print(f"  {n:2d} {t:12.7g} сут: p_wf {w.p_wf / BAR:7.2f} бар, q_o {w.q_o_std * DAY:9.4f}, "
          f"q_g {w.q_g_std * DAY:10.3f}, GOR {gor:8.3f}, dT_w {s.T[0] - T0:+.4f} К, "
          f"S_g(r_w) {s.Sg[0]:.4f}, газ {two.size:3d} яч., до {sim._grid.r_centers[two[-1]] if two.size else 0:.2f} м")
print("\nT(r_w), T_min, T_max по отметкам; S_g(r_w); граница двухфазной зоны")
r_c = sim._grid.r_centers
for d in [1 / 1440] + STABLE:
    s = hist.states[rec(d)]
    two = np.nonzero(s.Sg > 0)[0]
    edge = f"{r_c[two[-1]]:.2f} м" if two.size else "—"
    print(f"{d:9.5g} сут: T_w = {s.T[0]:.4f} К, T in [{s.T.min():.4f}, {s.T.max():.4f}], "
          f"S_g(r_w) = {s.Sg[0]:.4f}, p_max(газ) = {np.max(s.p[two]) / BAR if two.size else 0:.3f} бар, газ до {edge}")
