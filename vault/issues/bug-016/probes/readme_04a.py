"""BUG-016: утверждения README 04a о раннем переходном процессе — до и после.

Истории — regress/<метка>/04a_high_gas_saturation.npz (запись каждые 300 с).
Печатает: ячейки с газом на первой записи; максимум S_g(r_w) и его время;
изобару p_b (линейная интерполяция по ln r между центрами ячеек) — максимум за
первые сутки и положение на 12 и 72 ч; отклонение q_o от финального; монотонность T(r_w).
Запуск: python <этот файл> <метка> [<метка> ...]
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

NAME = "04a_high_gas_saturation"
PB = 15.0e6
DT_H = 300.0 / 3600.0                        # шаг записи, ч
cfg = load_config(patch.NS / "examples" / NAME / "config.json")
sim, _ = SimulatorFactory.from_config(cfg)
lr = np.log(sim._grid.r_centers)


def isobar(p):
    """r, где p = p_b: первая смена знака p - p_b от забоя."""
    s = p - PB
    k = np.nonzero((s[:-1] < 0) & (s[1:] >= 0))[0]
    if not k.size:
        return np.nan
    k = k[0]
    w = -s[k] / (s[k + 1] - s[k])
    return float(np.exp(lr[k] + w * (lr[k + 1] - lr[k])))


for label in sys.argv[1:]:
    d = np.load(HERE / "regress" / label / f"{NAME}.npz")
    p, sg, T, q_o = d["p"], d["Sg"], d["T"][:, 0], d["q_o"]
    n = len(T)
    rb = np.array([isobar(p[k]) for k in range(n)])
    k24 = int(round(24 / DT_H))
    kmax = 1 + int(np.nanargmax(rb[1:k24 + 1]))
    ks = int(np.argmax(sg[:, 0]))
    dev = {h: abs(q_o[int(round(h / DT_H))] / q_o[-1] - 1) * 100 for h in (1, 6, 24)}
    print(f"── {label}: записей {n}")
    print(f"  запись 1 (5 мин): ячеек S_g>0 {int((sg[1] > 0).sum())}, p<p_b {int((p[1] < PB).sum())}")
    print(f"  max S_g(r_w) = {sg[ks, 0]:.4f} на {ks * DT_H:.2f} ч")
    print(f"  изобара p_b: max {rb[kmax]:.2f} м на {kmax * DT_H:.2f} ч; 12 ч {rb[int(12 / DT_H)]:.3f} м; "
          f"72 ч {rb[-1]:.3f} м")
    print("  |q_o/q_o(72 ч) - 1|: " + ", ".join(f"{h} ч {v:.2f} %" for h, v in dev.items()))
    print(f"  T(r_w): 5 мин {T[1]:.3f}, рост с 5 мин монотонный: {bool(np.all(np.diff(T[1:]) >= 0))}; "
          f"min {T.min():.3f} на записи {int(np.argmin(T))}")
    print(f"  финал: p[0] {p[-1, 0] / 1e6:.3f} МПа, S_g max {sg[-1].max():.5f}, "
          f"ячеек p<p_b / S_g>0: {int((p[-1] < PB).sum())} / {int((sg[-1] > 0).sum())}")
