"""FEAT-032 (планирование): сводная таблица прогона ramp_probe.py по всем примерам.

Запуск: python summarize_sweep.py <файл .out.txt>
Строка таблицы: пример | h0 | исход | max|ΔT(r_w)| (момент) | max|ΔRs(r_w)| | max|Δp(r_w)| |
отказов | счёт против штатного.
"""

import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
orig_time = {}
rows = []
cur = None
for line in text:
    m = re.match(r"(\S+) orig: .*счёт ([\d.]+) с", line)
    if m:
        orig_time[m[1]] = float(m[2])
        continue
    m = re.match(r"(\S+) h0=([\d.]+) first=\d: .*счёт ([\d.]+) с, подшагов (\d+), отказов (\d+)", line)
    if m:
        cur = {"ex": m[1], "h0": m[2], "t": float(m[3]), "fails": m[5], "res": "ок"}
        rows.append(cur)
        continue
    m = re.match(r"(\S+) first=\d h0=([\d.]+): ОТКАЗ — .*t = ([\d.]+) сут", line)
    if m:
        rows.append({"ex": m[1], "h0": m[2], "res": f"ОТКАЗ при t = {m[3]} сут"})
        continue
    m = re.search(r"max\|ΔT\(r_w\)\| = ([\d.]+) К \(t = ([\d.]+) сут.*max\|ΔRs\(r_w\)\| = ([\d.]+).*"
                  r"max\|Δp\(r_w\)\| = ([\d.]+) бар.*на конце: ΔT = ([-+\d.]+) К", line)
    if m and cur is not None:
        cur.update(dT=m[1], tT=m[2], dRs=m[3], dp=m[4], dTend=m[5])

print("| пример | h0, с | исход | max|ΔT(r_w)|, К (t, сут) | max|ΔRs(r_w)| | max|Δp(r_w)|, бар "
      "| ΔT на конце, К | отказов | счёт / штатный |")
print("|---|---|---|---|---|---|---|---|---|")
for r in rows:
    if r["res"] != "ок":
        print(f"| {r['ex']} | {r['h0']} | **{r['res']}** | | | | | | |")
        continue
    ratio = r["t"] / max(orig_time.get(r["ex"], r["t"]), 1e-9)
    print(f"| {r['ex']} | {r['h0']} | ок | {r['dT']} ({r['tT']}) | {r['dRs']} | {r['dp']} "
          f"| {r['dTend']} | {r['fails']} | {ratio:.2f} |")
