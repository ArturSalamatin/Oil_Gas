"""BUG-021: меняются ли числа таблицы README 13b (раздел «Ожидаемое поведение») в пределах её точности.

Из историй history_<a>/13b_pwf_alternating.npz и history_<b>/... (history_snapshot.py): на записях
таблицы (запись n = 2·сут) q_o = −G_o[забой], GOR = G_g/G_o на забое, T(r_w), S_g(r_w), p у забоя,
число двухфазных ячеек — в формате README. Звёздочка — значение в этом формате различается.

Запуск: <python> <P>\\readme_13b.py base v2
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
a, b = (np.load(HERE / f"history_{t}" / "13b_pwf_alternating.npz") for t in sys.argv[1:3])
DAYS = (0.5, 1, 1.5, 2, 5, 7.5, 10, 15, 20, 25, 29, 29.5, 30)


PB = 15.0e6   # p_b конфига 13b (R_s0 = 30, таблица PVT), Па — для столбца «недонас.»


def row(h, n):
    go, gg = h["G_o"][n - 1][0], h["G_g"][n - 1][0]   # hydro_results[1:] — запись n ↔ индекс n-1
    under = (h["regime"][n] == 2) & (h["p"][n] < PB)   # однофазные ниже p_b — недонасыщенная нефть
    return [f"{-go:.4e}", f"{gg / go:.2f}", f"{h['T'][n][0]:.3f}", f"{h['Sg'][n][0]:.4f}",
            f"{h['p'][n][0] / 1e6:.4f}", f"{int(np.count_nonzero(h['regime'][n] == 1))}",
            f"{int(np.count_nonzero(under))}"]


print("сут | q_o | GOR | T(r_w) | Sg(r_w) | p у забоя, МПа | двухф. | недонас.")
changed = 0
for d in DAYS:
    n = int(round(2 * d))
    ra, rb = row(a, n), row(b, n)
    cells = [x if x == y else f"{x} → {y} *" for x, y in zip(ra, rb)]
    changed += sum(x != y for x, y in zip(ra, rb))
    print(f"{d:g} | " + " | ".join(cells))
print(f"различий в формате README: {changed}")
first = next((i for i in range(len(a["t"])) if not np.array_equal(a["p"][i], b["p"][i])), None)
print(f"первая различающаяся запись: {first} (t = {a['t'][first] / 86400:g} сут)" if first is not None else "записи совпадают")
print("max|Δp| по записям, Па:", " ".join(f"{np.max(np.abs(a['p'][i] - b['p'][i])):.0f}" for i in range(len(a["t"]))))
