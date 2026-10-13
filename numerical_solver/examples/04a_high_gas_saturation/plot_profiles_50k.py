"""Профили p, T, Sg, Rs — 10 кривых, равномерно на интервале 0…50000 с.

Штатный example_runner рисует только 4 момента, распределённых по всей
длине расчёта (3 суток). Здесь нужен другой срез: ранняя стадия, где
идёт основная релаксация давления и фронт разгазирования ещё движется —
в первый час изобара pb уходит до r ≈ 1.8 м и к 12 ч возвращается к ≈ 1.5 м.

Решатель не перезапускается — читается уже посчитанный
output/profiles.csv (865 записей × 150 ячеек, шаг 300 с). Число ячеек
берётся из самого файла, поэтому скрипт работает при любой сетке.
"""

from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent

from gpn_multiphase_solver.io.figures import save_figure, export_emf  # noqa: E402

CSV = HERE / "output" / "profiles.csv"
OUT = HERE / "output"

T_MAX = 50_000.0   # верх интервала, с
S_TO_DAY = 1.0 / 86400.0   # время на графиках — в сутках (FEAT-022)
N_CURVES = 10      # число кривых на рисунке

FIELDS = [
    ("p_Pa", "p, МПа", 1e-6, "Профили давления", "pressure_profiles_50k.png"),
    ("T_K", "T, К", 1.0, "Профили температуры", "temperature_profiles_50k.png"),
    ("Sg", "$S_g$", 1.0, "Профили газонасыщенности", "saturation_profiles_50k.png"),
    ("Rs", "$R_s$, м³ст/м³ст", 1.0, "Профили газосодержания", "rs_profiles_50k.png"),
]


def main() -> None:
    d = np.genfromtxt(CSV, delimiter=",", names=True)

    # profiles.csv — «длинная» таблица: на каждый шаг подряд идут все ячейки.
    # Число ячеек берём по числу разных r в первом блоке, а не из конфига.
    r_all = d["r_m"]
    n_cells = int(np.argmax(r_all[1:] < r_all[:-1]) + 1)
    n_steps = len(d) // n_cells

    r = r_all.reshape(n_steps, n_cells)[0]
    times = d["time_s"].reshape(n_steps, n_cells)[:, 0]

    # 10 целевых моментов, равномерно по 0…50000 с; для каждого берём
    # ближайшую сохранённую запись (шаг истории 300 с — попадание точное).
    targets = np.linspace(0.0, T_MAX, N_CURVES)
    idx = [int(np.argmin(np.abs(times - t))) for t in targets]

    colors = plt.cm.viridis(np.linspace(0.0, 0.92, len(idx)))

    for field, ylabel, scale, subtitle, fname in FIELDS:
        Y = d[field].reshape(n_steps, n_cells)

        fig, ax = plt.subplots(figsize=(7.5, 5))
        for c, i in zip(colors, idx):
            ax.semilogx(r, Y[i] * scale, color=c, lw=1.5,
                        label=f"t = {times[i] * S_TO_DAY:.4g} сут")
        ax.set_xlabel("r, м")
        ax.set_ylabel(ylabel)
        ax.set_title(f"04a: высокая газонасыщенность\n{subtitle} "
                     f"(0…{T_MAX * S_TO_DAY:.3g} сут)")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        fig.tight_layout()
        save_figure(fig, OUT / fname, dpi=110)
        plt.close(fig)
        print(f"  {fname}")

    # Четыре SVG — в EMF одним запуском Inkscape (FEAT-026).
    export_emf(OUT)

    print(f"Моменты, с: {[f'{times[i]:.0f}' for i in idx]}")


if __name__ == "__main__":
    main()
