"""BUG-016: числа README, зависящие от старта, — из историй regress/<метка>/.

  04a — таблица «Переходный процесс» (5 мин, 1 ч, 6 ч, 12 ч, 24 ч, 72 ч;
        запись каждые 300 с);
  11  — минимум T(r_w) в первые сутки и его момент (запись раз в час).

Запуск: python <этот файл> <метка> [<метка> ...]
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for label in sys.argv[1:]:
    d = np.load(HERE / "regress" / label / "04a_high_gas_saturation.npz")
    print(f"── {label}: 04a «Переходный процесс»")
    for name, k in (("5 мин", 1), ("1 ч", 12), ("6 ч", 72), ("12 ч", 144), ("24 ч", 288), ("72 ч", 864)):
        q_o, q_g = d["q_o"][k], d["q_g"][k]
        print(f"  {name:6s} S_g(r_w) {d['Sg'][k][0]:.3f}  q_o {q_o * 1e3:.2f}e-3  "
              f"GOR {q_g / q_o:.3f}  T(r_w) {d['T'][k][0]:.3f}")
    e = np.load(HERE / "regress" / label / "11_degassing_at_boundary.npz")
    Tw = e["T"][:25, 0]
    j = int(np.argmin(Tw))
    print(f"── {label}: 11 — min T(r_w) за первые сутки {Tw[j]:.3f} К на записи {j} (ч)")
