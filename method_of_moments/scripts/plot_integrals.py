"""Визуализация аналитических интегралов I_Φ(γ), I_S(γ,β), J(σ) (FEAT-004).

Запуск:
    cd method_of_moments
    .venv/Scripts/python scripts/plot_integrals.py

Результаты сохраняются в results/integrals/*.png и *.svg.
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from integrals import I_Phi, I_S, J

OUT_DIR = Path(__file__).resolve().parent.parent / "results" / "integrals"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "lines.linewidth": 1.5,
    "figure.dpi": 150,
})


def _save(fig, name):
    fig.savefig(OUT_DIR / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}.png, {name}.svg")


# ═══ 1. Три панели: I_Φ(γ), I_S(γ), J(σ) ═══════════════════════════════
def plot_integrals_combined():
    gamma = np.linspace(0.1, 5.0, 200)
    sigma = np.linspace(0.1, 5.0, 200)
    orders = [0, 1, 2, 3]
    beta = 2.0

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.5))

    for n in orders:
        y = [I_Phi(n, g) for g in gamma]
        ax1.plot(gamma, y, label=f"$n$ = {n}")
    ax1.set_xlabel("$\\gamma$")
    ax1.set_ylabel("$I_\\Phi^{(n)}$")
    ax1.set_title("$I_\\Phi^{(n)} = 1/(n\\gamma + 1)$")
    ax1.legend()

    for n in orders:
        y = [I_S(n, g, beta) for g in gamma]
        ax2.plot(gamma, y, label=f"$n$ = {n}")
    ax2.set_xlabel("$\\gamma$")
    ax2.set_ylabel("$I_S^{(n)}$")
    ax2.set_title(f"$I_S^{{(n)}}$ при $\\beta$ = {beta:.0f}")
    ax2.legend()

    for m in orders:
        y = [J(m, s) for s in sigma]
        ax3.plot(sigma, y, label=f"$m$ = {m}")
    ax3.set_xlabel("$\\sigma$")
    ax3.set_ylabel("$J^{(m)}$")
    ax3.set_title("$J^{(m)} = 2/(m+1) - 1/(m+\\sigma+1)$")
    ax3.legend()

    fig.tight_layout()
    _save(fig, "integrals_combined")


# ═══ 2. I_S: влияние β при фиксированном γ ══════════════════════════════
def plot_IS_beta_dependence():
    beta = np.linspace(0.0, 5.0, 200)
    orders = [0, 1, 2, 3]
    gamma = 1.0

    fig, ax = plt.subplots(figsize=(7, 5))
    for n in orders:
        y = [I_S(n, gamma, b) for b in beta]
        ax.plot(beta, y, label=f"$n$ = {n}")
    ax.set_xlabel("$\\beta$")
    ax.set_ylabel("$I_S^{(n)}$")
    ax.set_title(f"$I_S^{{(n)}}(\\beta)$ при $\\gamma$ = {gamma:.0f}")
    ax.legend()
    _save(fig, "IS_beta_dependence")


# ═══ main ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Сохранение в {OUT_DIR}/")
    plot_integrals_combined()
    plot_IS_beta_dependence()
    print("Готово.")
