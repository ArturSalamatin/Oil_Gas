"""BUG-016: сравнить два прогона regress_examples.py по всем примерам.

Запуск: python <этот файл> <метка_эталона> <метка>
Печатает: побитово ли, max|Δp| (Па), max|ΔS_g|, max|ΔT| (К), max|Δq_o|/q_o
по всей истории; число вызовов advance и отказов (дробление шага).
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
A, B = HERE / "regress" / sys.argv[1], HERE / "regress" / sys.argv[2]
print(f"{'пример':28s} {'побит.':>6s} {'|Δp|,Па':>9s} {'|ΔSg|':>9s} {'|ΔT|,К':>9s} "
      f"{'|Δq|/q':>9s}  advance(отказ) {sys.argv[1]} → {sys.argv[2]}   время")
for fa in sorted(A.glob("*.npz")):
    fb = B / fa.name
    if not fb.exists():
        print(f"{fa.stem:28s}  нет во втором прогоне")
        continue
    a, b = np.load(fa), np.load(fb)
    if a["p"].shape != b["p"].shape:
        print(f"{fa.stem:28s}  разная длина истории")
        continue
    same = all(np.array_equal(a[k], b[k]) for k in ("p", "Sg", "Rs", "T", "regime", "q_o", "q_g"))
    dp = np.abs(a["p"] - b["p"]).max()
    dsg = np.abs(a["Sg"] - b["Sg"]).max()
    dT = np.abs(a["T"] - b["T"]).max()
    qa = np.abs(a["q_o"]).max()
    dq = np.abs(a["q_o"] - b["q_o"]).max() / qa if qa > 0 else 0.0
    ca, cb = a["count"], b["count"]
    # Последняя запись: дискретизация старта к концу истории должна забыться
    fp = np.abs(a["p"][-1] - b["p"][-1]).max()
    fT = np.abs(a["T"][-1] - b["T"][-1]).max()
    fq = abs(a["q_o"][-1] - b["q_o"][-1]) / abs(a["q_o"][-1]) if a["q_o"][-1] else 0.0
    print(f"{fa.stem:28s} {'да' if same else 'нет':>6s} {dp:9.2e} {dsg:9.2e} {dT:9.2e} {dq:9.2e}  "
          f"{ca[0]}({ca[1]}) → {cb[0]}({cb[1]})   {float(a['time']):.1f} → {float(b['time']):.1f} с"
          f"   конец: |Δp| {fp:.1e} Па, |ΔT| {fT:.1e} К, Δq/q {fq:.1e}")
