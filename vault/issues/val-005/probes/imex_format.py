"""Проба VAL-005: формат нормализованного эталона IMEX T07 и сверка с golden/T07 прототипа."""
import csv
from collections import defaultdict
from pathlib import Path

SOLVER = Path.cwd()  # запускать из numerical_solver/
REG = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "regression"
print("REG =", REG)

imex = defaultdict(dict)  # (t, var) -> {cell: value}
dist = {}
with open(REG / "reference_imex_normalized" / "T07_profiles.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        imex[(r["time_day"], r["variable"])][int(r["cell"])] = float(r["value"])
        dist[int(r["cell"])] = float(r["imex_distance_m"])
times = sorted({t for t, _ in imex}, key=float)
vars_ = sorted({v for _, v in imex})
print("времена:", times)
print("переменные:", vars_)
print("ячейки:", min(dist), "...", max(dist), "; distance 1..5:", [dist[i] for i in range(1, 6)],
      "; 99..101:", [dist[i] for i in (99, 100, 101)])
for t in times:
    for v in vars_:
        col = imex[(t, v)]
        print(f"t={t} {v}: ячеек {len(col)} ({min(col)}..{max(col)}), 1..3 {[round(col[i], 4) for i in range(1, 4)]}, "
              f"100 {col.get(100)}, 101 {col.get(101)}")

gold = defaultdict(list)
with open(REG / "golden" / "T07" / "profiles.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        gold[r["time_day"]].append(r)
print("golden времена:", list(gold))

# ── Метрики golden/T07 против IMEX: ячейка i ↔ ячейка i, i = 1…100 ──
# Ключи времени у двух файлов разной точности — сопоставление по округлению до 1e-6 сут.
gkey = {round(float(t), 6): t for t in gold}
print(f"{'сут':>12} {'max|Δp|':>10} {'max|ΔSg|':>10} {'RMSE Sg':>10} {'max|ΔRs|':>10}")
for t in times:
    g = gold.get(gkey.get(round(float(t), 6)))
    if g is None:
        print(f"{t:>12} нет в golden")
        continue
    p_i, s_i, r_i = imex[(t, "P_bar")], imex[(t, "Sg")], imex[(t, "Rs")]
    dp = max(abs(float(x["pressure_bar"]) - p_i[i + 1]) for i, x in enumerate(g))
    ds = [float(x["Sg"]) - s_i[i + 1] for i, x in enumerate(g)]
    dr = max(abs(float(x["Rs"]) - r_i[i + 1]) for i, x in enumerate(g))
    rmse = (sum(d * d for d in ds) / len(ds)) ** 0.5
    print(f"{float(t):12.6g} {dp:10.4g} {max(map(abs, ds)):10.4g} {rmse:10.4g} {dr:10.4g}")

# ── Дебиты ──
ir = list(csv.DictReader(open(REG / "reference_imex_normalized" / "T07_rates.csv", newline="", encoding="utf-8")))
gr = {round(float(r["time_day"]), 6): r for r in csv.DictReader(open(REG / "golden" / "T07" / "rates.csv", newline="", encoding="utf-8"))}
print("IMEX rates времена:", [r["time_day"] for r in ir])
print(f"{'сут':>12} {'Δq_o,%':>9} {'Δq_g,%':>9} {'ΔGOR,%':>9} {'ΔBHP':>8}")
for r in ir:
    g = gr.get(round(float(r["time_day"]), 6))
    if g is None:
        continue
    vals = []
    for ik, gk in (("qo", "oil_rate_sm3_day"), ("qg", "gas_rate_sm3_day"), ("GOR", "GOR_sm3_sm3")):
        x, y = float(r[ik]), float(g[gk])
        vals.append(100 * (y - x) / x)
    print(f"{float(r['time_day']):12.6g} {vals[0]:9.3f} {vals[1]:9.3f} {vals[2]:9.3f} "
          f"{float(g['BHP_bar']) - float(r['BHP_bar']):8.3f}")
