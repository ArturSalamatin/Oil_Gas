"""BUG-022: наибольшие отличия историй вариантов от базы по всем примерам (hist_*.npz пишет cell_tol.py).

Запуск (из этого каталога): ..\..\..\..\numerical_solver\.venv\Scripts\python diff_table.py pv1e-8
"""
import sys
from pathlib import Path
import numpy as np

for _s in (sys.stdout,):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
v = sys.argv[1]
lines = [f"вариант {v} против 0: max по истории (на последней записи); p — бар, T — К; q_o — отн."]
lines.append(f"{'пример':<28}{'|Δp|':>20}{'|ΔT|':>20}{'|ΔS_g|':>20}{'|ΔR_s|':>20}{'|Δq_o|/q':>10}")
for fa in sorted(HERE.glob("hist_*_0.npz")):
    name = fa.name[len("hist_"):-len("_0.npz")]
    fb = HERE / f"hist_{name}_{v}.npz"
    if not fb.exists():
        continue
    a, b = np.load(fa), np.load(fb)
    cells = []
    for k, s in (("p", 1e5), ("T", 1.0), ("Sg", 1.0), ("Rs", 1.0)):
        d = np.abs(a[k] - b[k]) / s
        cells.append(f"{d.max():9.1e} ({d[-1].max():7.1e})")
    qa = np.abs(a["q_o"]).max()
    dq = np.abs(a["q_o"] - b["q_o"]).max() / qa if qa > 0 else 0.0
    lines.append(f"{name:<28}" + "".join(f"{c:>20}" for c in cells) + f"{dq:10.1e}")
text = "\n".join(lines)
print(text)
(HERE / f"diff_table_{v}.out.txt").write_text(text + "\n", encoding="utf-8")
