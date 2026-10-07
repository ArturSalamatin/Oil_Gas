"""BUG-016: числа README 12 — таблица по суткам, забой на 15 сут, ячейка N-1 — до и после.

Истории — regress/<метка>/12_large_drainage_radius.npz (запись раз в сутки).
Сетка — из конфига примера дерева $env:BUG016_NS (через patch.NS).
Запуск: python <этот файл> <метка до> <метка после>
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

NAME = "12_large_drainage_radius"
DAYS = (1, 2, 3, 4, 5, 6, 7, 10, 12, 13, 15)
cfg = load_config(patch.NS / "examples" / NAME / "config.json")
sim, _ = SimulatorFactory.from_config(cfg)
rc = sim._grid.r_centers
j1 = int(np.argmin(np.abs(rc - 1.0)))      # ячейка с центром около 1 м
pb = 15.0e6


def table(label):
    d = np.load(HERE / "regress" / label / f"{NAME}.npz")
    p, sg, T, q_o, q_g, Rs = d["p"], d["Sg"], d["T"], d["q_o"], d["q_g"], d["Rs"]
    rows = {}
    for k in DAYS:
        two = np.nonzero(sg[k] > 0)[0]
        front = rc[two.max()] if two.size else 0.0
        rows[k] = (f"{q_o[k] * 1e3:.4f}", f"{q_g[k] / q_o[k]:.2f}", f"{T[k][0]:.3f}",
                   f"{sg[k][0]:.4f}", str(two.size), f"{front:.1f}",
                   f"{p[k][j1] / 1e6:.4f}", f"{p[k][-1] / 1e6:.4f}")
    k = 15
    extra = {
        "p у забоя, МПа": f"{p[k][0] / 1e6:.3f}", "R_s(r_w)": f"{Rs[k][0]:.3f}",
        "T(r_w)": f"{T[k][0]:.3f}", "q_o": f"{q_o[k]:.4e}", "q_g": f"{q_g[k]:.5f}",
        "min_t p_N-1 - p_b, кПа (сут)": f"{(p[:, -1].min() - pb) / 1e3:+.0f} ({int(np.argmin(p[:, -1]))})",
        "max S_g,N-1": f"{sg[:, -1].max():.1e}",
        "T min по записям (сут)": f"{T[1:, 0].min():.3f} ({1 + int(np.argmin(T[1:, 0]))})",
    }
    return rows, extra


(ra, ea), (rb, eb) = table(sys.argv[1]), table(sys.argv[2])
cols = ("q_o", "GOR", "T", "Sg", "ячеек", "фронт", "p(1м)", "p_N-1")
print(f"ячейка у 1 м: j = {j1}, r = {rc[j1]:.3f} м")
for k in DAYS:
    diff = [f"{c}: {x} → {y}" for c, x, y in zip(cols, ra[k], rb[k]) if x != y]
    print(f"сут {k:>2}: " + ("; ".join(diff) if diff else "без изменений") + f"   [{' | '.join(rb[k])}]")
for key in ea:
    mark = "   " if ea[key] == eb[key] else ">> "
    print(f"{mark}{key}: {ea[key]} | {eb[key]}")
