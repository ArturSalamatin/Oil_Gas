"""Эталонные числа README примера 22 (FEAT-036) из вывода его расчёта.

Читает well_history.csv и profiles.csv каталога вывода примера (аргумент) и
печатает: забой по записям (p_wf, T_wf, q_o, q_g, GOR), крайние T_wf,
двухфазную зону и профиль T на последней записи.
Запуск: <PY> example22_numbers.py <каталог вывода примера 22>
"""

import csv
import sys
from pathlib import Path

out = Path(sys.argv[1])
DAY = 86400.0

with open(out / "well_history.csv", encoding="utf-8", newline="") as f:
    well = [{k: float(v) if v else None for k, v in row.items()} for row in csv.DictReader(f)]
with open(out / "profiles.csv", encoding="utf-8", newline="") as f:
    prof = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]

lines = ["забой по записям: t, сут | p_wf, МПа | T_wf, К | q_o, м³ст/сут | q_g, м³ст/сут | GOR"]
for w in well:
    gor = w["GOR_m3st_m3st"]
    lines.append(f"  {w['time_day']:9.5f} | {w['p_wf_Pa'] / 1e6:7.3f} | {w['T_wf_K']:8.4f} | "
                 f"{w['q_o_m3st_s'] * DAY:8.4f} | {w['q_g_m3st_s'] * DAY:9.3f} | "
                 f"{gor if gor is None else round(gor, 3)}")
tmin = min(well, key=lambda w: w["T_wf_K"])
tmax = max(well, key=lambda w: w["T_wf_K"])
lines.append(f"T_wf min {tmin['T_wf_K']:.4f} К при {tmin['time_day']:.5f} сут; "
             f"max {tmax['T_wf_K']:.4f} К при {tmax['time_day']:.5f} сут")

last_step = max(r["step"] for r in prof)
last = [r for r in prof if r["step"] == last_step]
gas = [r for r in last if r["Sg"] > 1e-8]
lines.append(f"последняя запись (шаг {int(last_step)}, {last[0]['time_s'] / DAY:.3f} сут): "
             f"ячеек с газом {len(gas)}, двухфазная зона до r = "
             f"{max(r['r_m'] for r in gas) if gas else 0:.3f} м; S_g у забоя {last[0]['Sg']:.5f}")
tl = min(last, key=lambda r: r["T_K"])
th = max(last, key=lambda r: r["T_K"])
lines.append(f"  T: min {tl['T_K']:.4f} К при r = {tl['r_m']:.3f} м; "
             f"max {th['T_K']:.4f} К при r = {th['r_m']:.3f} м")
for day in (5.0, 15.0):
    rows = [r for r in prof if abs(r["time_s"] / DAY - day) < 1e-6]
    g = [r for r in rows if r["Sg"] > 1e-8]
    if rows:
        lines.append(f"  {day:g} сут: двухфазная зона до r = {max(r['r_m'] for r in g) if g else 0:.3f} м, "
                     f"S_g у забоя {rows[0]['Sg']:.5f}, T у забоя {rows[0]['T_K']:.4f} К")
print("\n".join(lines))
