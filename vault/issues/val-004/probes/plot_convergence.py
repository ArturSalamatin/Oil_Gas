"""VAL-004: рисунок сходимости по шагу — |u − предел| на 1 ч останова от наибольшего шага первого часа.

Читает npz dt_series.py (как limits.py) и пишет convergence.png рядом
(в git не идёт). Ось x — длина шага Δt, с (не время расчёта). Пустые
маркеры — прогоны с отказами гидродинамики: фактические шаги раздроблены
и не равны заданным (dt_series_1h_rerun.out.txt, dt_series_1h_fine.out.txt,
dt_series_1h_g9.out.txt). Пределы — равномерное сгущение до 0.88 с
(limits.out.txt; те же числа — P_LIM, T_LIM в tests/test_val004.py).

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\val-004\\probes\\plot_convergence.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
LIM = {"p": 185.4611262, "T": 398.0232431}        # бар, К
SCALE = {"p": 1e5, "T": 1.0}
LABEL = {"p": r"$|p(r_w) - p^*|$, бар", "T": r"$|T(r_w) - T^*|$, К"}
# Прогоны с отказами (подшаги не равны заданным) — по выводам dt_series.py
UNI_FAILED = {1, 2, 3, 4, 5, 7, 8}
GRD_FAILED = {0, 1, 2, 3}


def load(files):
    out = {}
    for name in files:
        z = np.load(HERE / name)
        for key in z.files:
            k, rest = key.split("_", 1)
            if rest.startswith("1h_"):
                out.setdefault(int(k[1:]), {})[rest[3:]] = z[key]
    return out


def main():
    uni = load(["dt_series_W1h_k0-9.npz", "dt_series_W1h_k10-12.npz"])
    grd = load(["dt_series_W1h_k0-5_g9.npz", "dt_series_W1h_k4-6_g9.npz"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, f in zip(axes, ("p", "T")):
        for name, d, h_of, failed, color in (
                ("равномерно, шаг 3600/2^k", uni, lambda k: 3600 / 2 ** k, UNI_FAILED, "C0"),
                ("нарастающие от 3600/2^(9+k), наибольший 1800/2^k", grd,
                 lambda k: 1800 / 2 ** k, GRD_FAILED, "C3")):
            ks = sorted(d)
            h = np.array([h_of(k) for k in ks])
            e = np.array([abs(d[k][f][0] / SCALE[f] - LIM[f]) for k in ks])
            ax.plot(h, e, "-", color=color, lw=0.8, alpha=0.6)
            ok = np.array([k not in failed for k in ks])
            ax.plot(h[ok], e[ok], "o", color=color, label=name)
            ax.plot(h[~ok], e[~ok], "o", mfc="none", color=color)
        # Наклон 1 (первый порядок) через последнюю точку равномерной серии
        h0 = 3600 / 2 ** 12
        e0 = abs(uni[12][f][0] / SCALE[f] - LIM[f])
        hh = np.array([h0, 3600.0])
        ax.plot(hh, e0 * hh / h0, "k--", lw=0.8, label="наклон 1")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(r"$\Delta t$, с")
        ax.set_ylabel(LABEL[f])
        ax.grid(True, which="both", alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.suptitle("VAL-004: ошибка на 1 ч останова (bug020_rs150); пустые маркеры — шаги раздроблены")
    fig.tight_layout()
    fig.savefig(HERE / "convergence.png", dpi=150)
    print(f"записан {HERE / 'convergence.png'}")


if __name__ == "__main__":
    main()
