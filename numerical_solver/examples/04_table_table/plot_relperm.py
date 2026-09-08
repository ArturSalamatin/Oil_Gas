"""График табличных ОФП примера 04 (relperm.csv).

Таблица читается ровно так, как её видит решатель: TabulatedRelPerm
прототипа делает ЛИНЕЙНУЮ интерполяцию между узлами, поэтому кривая —
ломаная, а не гладкая. Это важно: излом kro/krg в узле напрямую
порождает излом подвижности в уравнении фильтрации.

На график наносится и рабочий диапазон расчёта: Sg в примере 04 не
превышает 0.0147, то есть решение живёт на ПЕРВОМ отрезке таблицы,
между узлами Sg = 0 и Sg = 0.1. Все остальные строки relperm.csv
в этом сценарии не используются вовсе.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\plot_relperm.py
"""

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).parent


def load_table():
    """Узлы relperm.csv: Sg, kro, krg."""
    rows = list(csv.reader(open(HERE / "relperm.csv")))[1:]
    return (np.array([float(r[0]) for r in rows]),
            np.array([float(r[1]) for r in rows]),
            np.array([float(r[2]) for r in rows]))


def working_range():
    """Диапазон Sg, фактически достигнутый в расчёте (из profiles.csv)."""
    path = HERE / "output/profiles.csv"
    if not path.exists():
        return None
    rows = list(csv.DictReader(open(path)))
    last = max(int(r["step"]) for r in rows)
    Sg = np.array([float(r["Sg"]) for r in rows if int(r["step"]) == last])
    return float(Sg.min()), float(Sg.max())


def main():
    Sg, kro, krg = load_table()
    rng = working_range()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # ── Панель 1: кривые целиком ─────────────────────────────────
    # Линейная интерполяция — та же, что применяет решатель
    Sg_fine = np.linspace(Sg[0], Sg[-1], 400)
    ax1.plot(Sg_fine, np.interp(Sg_fine, Sg, kro), "-", color="C3", lw=2,
             label=r"$k_{ro}$ (нефть)")
    ax1.plot(Sg_fine, np.interp(Sg_fine, Sg, krg), "-", color="C0", lw=2,
             label=r"$k_{rg}$ (газ)")
    # Узлы таблицы: между ними интерполяция линейна, в них — изломы
    ax1.plot(Sg, kro, "o", color="C3", ms=7, zorder=5)
    ax1.plot(Sg, krg, "o", color="C0", ms=7, zorder=5)

    if rng is not None:
        ax1.axvspan(rng[0], rng[1], color="C2", alpha=0.18,
                    label=f"рабочий диапазон: $S_g \\leq {rng[1]:.4f}$")

    ax1.set_xlabel("$S_g$")
    ax1.set_ylabel("относительная проницаемость")
    ax1.set_title("Табличные ОФП примера 04 (relperm.csv)\n"
                  "точки — узлы таблицы, между ними линейная интерполяция")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # ── Панель 2: увеличение на рабочем диапазоне ────────────────
    # Расчёт использует только первый отрезок таблицы — важно видеть,
    # что кривые там линейны, а krg мал (0.01 при Sg = 0.1).
    Sg_max_plot = 0.1
    Sg_zoom = np.linspace(0.0, Sg_max_plot, 200)
    ax2.plot(Sg_zoom, np.interp(Sg_zoom, Sg, kro), "-", color="C3", lw=2,
             label=r"$k_{ro}$")
    ax2.plot(Sg_zoom, np.interp(Sg_zoom, Sg, krg), "-", color="C0", lw=2,
             label=r"$k_{rg}$")
    ax2.plot([0.0, 0.1], [kro[0], kro[1]], "o", color="C3", ms=7, zorder=5)
    ax2.plot([0.0, 0.1], [krg[0], krg[1]], "o", color="C0", ms=7, zorder=5)

    if rng is not None:
        ax2.axvspan(rng[0], rng[1], color="C2", alpha=0.18)
        ax2.axvline(rng[1], color="C2", lw=1.2, ls="--",
                    label=f"$S_g^{{max}}$ = {rng[1]:.4f}")
        kro_w = float(np.interp(rng[1], Sg, kro))
        krg_w = float(np.interp(rng[1], Sg, krg))
        ax2.annotate(f"$k_{{ro}}$ = {kro_w:.4f}", xy=(rng[1], kro_w),
                     xytext=(rng[1] + 0.012, kro_w - 0.06), fontsize=9,
                     color="C3", arrowprops=dict(arrowstyle="->", color="C3"))
        ax2.annotate(f"$k_{{rg}}$ = {krg_w:.2e}", xy=(rng[1], krg_w),
                     xytext=(rng[1] + 0.012, krg_w + 0.10), fontsize=9,
                     color="C0", arrowprops=dict(arrowstyle="->", color="C0"))

    ax2.set_xlim(0.0, Sg_max_plot)
    ax2.set_xlabel("$S_g$")
    ax2.set_ylabel("относительная проницаемость")
    ax2.set_title("Первый отрезок таблицы\n"
                  "расчёт не выходит за его пределы")
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=9)

    fig.tight_layout()
    out = HERE / "output/relperm_table.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)

    # ── Сводка в консоль ─────────────────────────────────────────
    print("Узлы relperm.csv:")
    print("   Sg      kro      krg     krg/kro")
    for s, o, g in zip(Sg, kro, krg):
        ratio = f"{g / o:.4f}" if o > 0 else "  inf"
        print(f"  {s:.2f}   {o:.2f}    {g:.2f}   {ratio}")

    if rng is not None:
        print()
        print(f"Рабочий диапазон расчёта: Sg = {rng[0]:.6f} … {rng[1]:.6f}")
        print(f"  kro({rng[1]:.4f}) = {np.interp(rng[1], Sg, kro):.5f}")
        print(f"  krg({rng[1]:.4f}) = {np.interp(rng[1], Sg, krg):.5e}")
        print("  => решение лежит на первом отрезке таблицы (Sg = 0 … 0.1);")
        print("     остальные строки relperm.csv в этом сценарии не задействованы.")

    print(f"\nграфик: {out}")


if __name__ == "__main__":
    main()
