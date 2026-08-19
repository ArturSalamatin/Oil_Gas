"""Визуализация ОФП Кори и подвижностей (FEAT-002).

Запуск:
    cd method_of_moments
    .venv/Scripts/python scripts/plot_relperm.py

Результаты сохраняются в results/relperm/*.png и *.svg.
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pvt.black_oil import BlackOilFluid

# ─── Параметры (baseline) ──────────────────────────────────────────────
RHO_O_ST = 850.0
RHO_G_ST = 0.85
P_B = 18e6
T_0 = 350.0

RELPERM = {"S_or": 0.0, "S_gc": 0.00,
           "n_o": 1.0, "n_g": 1.0,
           "k_ro_max": 1.0, "k_rg_max": 1.0}

FLUID = BlackOilFluid({"rho_o_st": RHO_O_ST, "rho_g_st": RHO_G_ST},
                      P_B, T_0, relperm_config=RELPERM)

K_ABS = 1e-13  # м²

OUT_DIR = Path(__file__).resolve().parent.parent / "results" / "relperm"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Общие настройки графиков ───────────────────────────────────────────
plt.rcParams.update({
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "lines.linewidth": 1.5,
    "figure.figsize": (7, 5),
    "figure.dpi": 150,
})


def _save(fig, name):
    fig.savefig(OUT_DIR / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}.png, {name}.svg")


# ═══ 1. kro(Sg), krg(Sg) ═══════════════════════════════════════════════
def plot_kro_krg():
    Sg = np.linspace(0, 1.0 - RELPERM["S_or"], 300)
    kro = [FLUID.kro(s) for s in Sg]
    krg = [FLUID.krg(s) for s in Sg]

    fig, ax = plt.subplots()
    ax.plot(Sg, kro, label="$k_{ro}(S_g)$")
    ax.plot(Sg, krg, label="$k_{rg}(S_g)$")
    ax.axvline(RELPERM["S_gc"], color="gray", ls=":", lw=0.8, label=f"$S_{{gc}}$ = {RELPERM['S_gc']}")
    ax.axvline(1.0 - RELPERM["S_or"], color="gray", ls="--", lw=0.8, label=f"$1 - S_{{or}}$ = {1.0 - RELPERM['S_or']}")
    ax.set_xlabel("Газонасыщенность $S_g$")
    ax.set_ylabel("Относительная проницаемость")
    ax.set_title(f"ОФП Кори ($n_o$={RELPERM['n_o']}, $n_g$={RELPERM['n_g']})")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.legend()
    _save(fig, "kro_krg_vs_Sg")


# ═══ 2. kro, krg при разных показателях степени ════════════════════════
def plot_kro_krg_exponents():
    Sg = np.linspace(0, 1.0 - RELPERM["S_or"], 300)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    for n in [1.0, 2.0, 3.0, 4.0]:
        cfg = {**RELPERM, "n_o": n}
        f = BlackOilFluid({"rho_o_st": RHO_O_ST, "rho_g_st": RHO_G_ST},
                          P_B, T_0, relperm_config=cfg)
        kro = [f.kro(s) for s in Sg]
        ax1.plot(Sg, kro, label=f"$n_o$ = {n}")

    ax1.set_xlabel("$S_g$")
    ax1.set_ylabel("$k_{ro}$")
    ax1.set_title("$k_{ro}(S_g)$ при разных $n_o$")
    ax1.legend()

    for n in [1.0, 2.0, 3.0, 4.0]:
        cfg = {**RELPERM, "n_g": n}
        f = BlackOilFluid({"rho_o_st": RHO_O_ST, "rho_g_st": RHO_G_ST},
                          P_B, T_0, relperm_config=cfg)
        krg = [f.krg(s) for s in Sg]
        ax2.plot(Sg, krg, label=f"$n_g$ = {n}")

    ax2.set_xlabel("$S_g$")
    ax2.set_ylabel("$k_{rg}$")
    ax2.set_title("$k_{rg}(S_g)$ при разных $n_g$")
    ax2.legend()

    fig.tight_layout()
    _save(fig, "kro_krg_exponents")


# ═══ 3. Подвижности λo(Sg), λg(Sg) ════════════════════════════════════
def plot_mobilities():
    Sg = np.linspace(0, 1.0 - RELPERM["S_or"], 300)
    P = 15e6

    lam_o = [FLUID.mobility_o(P, T_0, s, K_ABS) for s in Sg]
    lam_g = [FLUID.mobility_g(P, T_0, s, K_ABS) for s in Sg]

    fig, ax = plt.subplots()
    ax.plot(Sg, lam_o, label="$\\lambda_o(S_g)$")
    ax.plot(Sg, lam_g, label="$\\lambda_g(S_g)$")
    ax.set_xlabel("$S_g$")
    ax.set_ylabel("Подвижность, м²/(Па·с)")
    ax.set_title(f"Подвижности фаз, $p$ = {P/1e6:.0f} МПа, $T$ = {T_0} К")
    ax.legend()
    _save(fig, "mobilities_vs_Sg")


# ═══ 4. Суммарная приведённая подвижность Λ(Sg) ═══════════════════════
def plot_Lambda():
    Sg = np.linspace(0, 1.0 - RELPERM["S_or"], 300)
    P = 15e6

    Lambda = [FLUID.Lambda(P, T_0, s, K_ABS) for s in Sg]

    fig, ax = plt.subplots()
    ax.plot(Sg, Lambda)
    ax.set_xlabel("$S_g$")
    ax.set_ylabel("$\\Lambda$, м²/(Па·с)")
    ax.set_title(f"Суммарная приведённая подвижность $\\Lambda(S_g)$, $p$ = {P/1e6:.0f} МПа")
    _save(fig, "Lambda_vs_Sg")


# ═══ 5. Λ(Sg) при разных давлениях ════════════════════════════════════
def plot_Lambda_pressures():
    Sg = np.linspace(0, 1.0 - RELPERM["S_or"], 300)

    fig, ax = plt.subplots()
    for P in [5e6, 10e6, 15e6, 20e6]:
        Lambda = [FLUID.Lambda(P, T_0, s, K_ABS) for s in Sg]
        ax.plot(Sg, Lambda, label=f"$p$ = {P/1e6:.0f} МПа")
    ax.set_xlabel("$S_g$")
    ax.set_ylabel("$\\Lambda$, м²/(Па·с)")
    ax.set_title(f"$\\Lambda(S_g)$ при разных давлениях, $T$ = {T_0} К")
    ax.legend()
    _save(fig, "Lambda_vs_Sg_pressures")


# ═══ 6. Долевой поток fo(Sg) ═══════════════════════════════════════════
def plot_fractional_flow():
    Sg = np.linspace(0, 1.0 - RELPERM["S_or"], 300)
    P = 15e6

    fo = []
    for s in Sg:
        lam_o = FLUID.mobility_o(P, T_0, s, K_ABS)
        lam_g = FLUID.mobility_g(P, T_0, s, K_ABS)
        total = lam_o + lam_g
        fo.append(lam_o / total if total > 0 else 1.0)

    fig, ax = plt.subplots()
    ax.plot(Sg, fo)
    ax.set_xlabel("$S_g$")
    ax.set_ylabel("$f_o = \\lambda_o / (\\lambda_o + \\lambda_g)$")
    ax.set_title(f"Долевой поток нефти, $p$ = {P/1e6:.0f} МПа")
    ax.set_ylim(0, 1.05)
    _save(fig, "fractional_flow_oil")


# ═══ main ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Сохранение в {OUT_DIR}/")
    plot_kro_krg()
    plot_kro_krg_exponents()
    plot_mobilities()
    plot_Lambda()
    plot_Lambda_pressures()
    plot_fractional_flow()
    print("Готово: 6 графиков × 2 формата (png + svg) = 12 файлов.")
