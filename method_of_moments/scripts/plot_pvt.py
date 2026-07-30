"""Визуализация PVT-корреляций Black Oil (FEAT-001).

Запуск:
    cd method_of_moments
    .venv/Scripts/python scripts/plot_pvt.py

Результаты сохраняются в results/pvt/*.png и *.svg.
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pvt import correlations as cor
from pvt.black_oil import BlackOilFluid

# ─── Параметры (baseline) ──────────────────────────────────────────────
RHO_O_ST = 850.0   # кг/м³
RHO_G_ST = 0.85    # кг/м³
P_B = 18e6          # Па
T_0 = 350.0         # К

FLUID = BlackOilFluid({"rho_o_st": RHO_O_ST, "rho_g_st": RHO_G_ST}, P_B, T_0)

OUT_DIR = Path(__file__).resolve().parent.parent / "results" / "pvt"
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


# ═══ 1. Rs(p) при разных T ═════════════════════════════════════════════
def plot_Rs():
    p = np.linspace(1e6, 25e6, 300)
    fig, ax = plt.subplots()
    for T in [320, 350, 380]:
        Rs_vals = [FLUID.Rs(pi, T) for pi in p]
        ax.plot(p / 1e6, Rs_vals, label=f"T = {T} К")
    ax.axvline(P_B / 1e6, color="k", ls="--", lw=0.8, label=f"$p_b$ = {P_B/1e6:.0f} МПа")
    ax.set_xlabel("Давление, МПа")
    ax.set_ylabel("$R_s$, м³ст/м³ст")
    ax.set_title("Газосодержание $R_s(p)$ — Standing")
    ax.legend()
    _save(fig, "Rs_vs_p")


# ═══ 2. Bo(p) ══════════════════════════════════════════════════════════
def plot_Bo():
    p = np.linspace(1e6, 25e6, 300)
    fig, ax = plt.subplots()
    for T in [320, 350, 380]:
        Bo_vals = [FLUID.Bo(pi, T) for pi in p]
        line, = ax.plot(p / 1e6, Bo_vals, label=f"T = {T} К")
        pb_T = FLUID.pb(T)
        ax.axvline(pb_T / 1e6, color=line.get_color(), ls="--", lw=0.8)
    ax.plot([], [], color="k", ls="--", lw=0.8, label="$p_b(T)$")
    ax.set_xlabel("Давление, МПа")
    ax.set_ylabel("$B_o$, м³пл/м³ст")
    ax.set_title("Объёмный коэффициент нефти $B_o(p)$ — Standing")
    ax.legend()
    _save(fig, "Bo_vs_p")


# ═══ 3. Bg(p) ══════════════════════════════════════════════════════════
def plot_Bg():
    p = np.linspace(1e6, 25e6, 300)
    fig, ax = plt.subplots()
    for T in [320, 350, 380]:
        Bg_vals = [cor.Bg(pi, T) for pi in p]
        ax.plot(p / 1e6, Bg_vals, label=f"T = {T} К")
    ax.set_xlabel("Давление, МПа")
    ax.set_ylabel("$B_g$, м³пл/м³ст")
    ax.set_title("Объёмный коэффициент газа $B_g(p)$ — идеальный газ")
    ax.legend()
    _save(fig, "Bg_vs_p")


# ═══ 4. Вязкость нефти ═════════════════════════════════════════════════
def plot_mu_o():
    T_arr = np.linspace(300, 420, 200)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # 4a: μ_od(T)
    mu_od = [cor.mu_dead_oil(Ti, RHO_O_ST) * 1e3 for Ti in T_arr]
    ax1.plot(T_arr, mu_od)
    ax1.set_xlabel("Температура, К")
    ax1.set_ylabel("$\\mu_{od}$, сП")
    ax1.set_title("Вязкость мёртвой нефти (Beggs–Robinson)")

    # 4b: μ_o(T) при разных Rs
    for Rs_m3 in [50, 200, 400]:
        mu_live = [cor.mu_o(Ti, Rs_m3, RHO_O_ST) * 1e3 for Ti in T_arr]
        ax2.plot(T_arr, mu_live, label=f"$R_s$ = {Rs_m3} м³/м³")
    ax2.set_xlabel("Температура, К")
    ax2.set_ylabel("$\\mu_o$, сП")
    ax2.set_title("Вязкость живой нефти (Beggs et al.)")
    ax2.legend()

    fig.tight_layout()
    _save(fig, "mu_oil")


# ═══ 5. Вязкость газа ══════════════════════════════════════════════════
def plot_mu_g():
    p = np.linspace(1e6, 30e6, 300)
    fig, ax = plt.subplots()
    for T in [320, 350, 380]:
        mu_vals = [cor.mu_g(pi, T, RHO_G_ST) * 1e3 for pi in p]
        ax.plot(p / 1e6, mu_vals, label=f"T = {T} К")
    ax.set_xlabel("Давление, МПа")
    ax.set_ylabel("$\\mu_g$, сП")
    ax.set_title("Вязкость газа (Lee–Gonzalez–Eakin)")
    ax.legend()
    _save(fig, "mu_gas")


# ═══ 6. Плотности ══════════════════════════════════════════════════════
def plot_densities():
    p = np.linspace(1e6, 25e6, 300)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    rho_o = [FLUID.rho_o(pi, T_0) for pi in p]
    ax1.plot(p / 1e6, rho_o)
    ax1.axvline(P_B / 1e6, color="k", ls="--", lw=0.8, label="$p_b$")
    ax1.set_xlabel("Давление, МПа")
    ax1.set_ylabel("$\\rho_o$, кг/м³")
    ax1.set_title(f"Плотность нефти, T = {T_0} К")
    ax1.legend()

    rho_g = [FLUID.rho_g(pi, T_0) for pi in p]
    ax2.plot(p / 1e6, rho_g)
    ax2.set_xlabel("Давление, МПа")
    ax2.set_ylabel("$\\rho_g$, кг/м³")
    ax2.set_title(f"Плотность газа, T = {T_0} К")

    fig.tight_layout()
    _save(fig, "densities")


# ═══ 7. co_sat, beta_o_sat ═════════════════════════════════════════════
def plot_saturated_derivatives():
    p = np.linspace(5e6, P_B - 1e5, 200)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    co_sat = [FLUID.co_sat(pi, T_0) for pi in p]
    co_plain = [FLUID.co(pi, T_0) for pi in p]
    ax1.plot(p / 1e6, [c * 1e9 for c in co_sat], label="$c_{o,sat}$")
    ax1.plot(p / 1e6, [c * 1e9 for c in co_plain], "--", label="$c_o$ (фикс. $R_s$)")
    ax1.set_xlabel("Давление, МПа")
    ax1.set_ylabel("$c_o$, $\\times 10^{-9}$ Па$^{-1}$")
    ax1.set_title("Сжимаемость нефти вдоль кривой насыщения")
    ax1.legend()

    beta_o_sat = [FLUID.beta_o_sat(pi, T_0) for pi in p]
    beta_o = [FLUID.beta_o(pi, T_0) for pi in p]
    ax2.plot(p / 1e6, [b * 1e3 for b in beta_o_sat], label="$\\beta_{o,sat}$")
    ax2.plot(p / 1e6, [b * 1e3 for b in beta_o], "--", label="$\\beta_o$ (фикс. $R_s$)")
    ax2.set_xlabel("Давление, МПа")
    ax2.set_ylabel("$\\beta_o$, $\\times 10^{-3}$ К$^{-1}$")
    ax2.set_title("Коэффициент расширения нефти")
    ax2.legend()

    fig.tight_layout()
    _save(fig, "saturated_derivatives")


# ═══ 8. Производные dRs/dp, dRs/dT ════════════════════════════════════
def plot_dRs():
    p = np.linspace(1e6, 25e6, 300)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    dRs_dp = [FLUID.dRs_dp(pi, T_0) for pi in p]
    ax1.plot(p / 1e6, dRs_dp)
    ax1.axvline(P_B / 1e6, color="k", ls="--", lw=0.8, label="$p_b$")
    ax1.set_xlabel("Давление, МПа")
    ax1.set_ylabel("$\\partial R_s / \\partial p$, м³/(м³·Па)")
    ax1.set_title(f"$\\partial R_s / \\partial p$, T = {T_0} К")
    ax1.legend()

    dRs_dT = [FLUID.dRs_dT(pi, T_0) for pi in p]
    ax2.plot(p / 1e6, dRs_dT)
    ax2.axvline(P_B / 1e6, color="k", ls="--", lw=0.8, label="$p_b$")
    ax2.set_xlabel("Давление, МПа")
    ax2.set_ylabel("$\\partial R_s / \\partial T$, м³/(м³·К)")
    ax2.set_title(f"$\\partial R_s / \\partial T$, T = {T_0} К")
    ax2.legend()

    fig.tight_layout()
    _save(fig, "dRs_derivatives")


# ═══ main ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Сохранение в {OUT_DIR}/")
    plot_Rs()
    plot_Bo()
    plot_Bg()
    plot_mu_o()
    plot_mu_g()
    plot_densities()
    plot_saturated_derivatives()
    plot_dRs()
    print("Готово: 8 графиков × 2 формата (png + svg) = 16 файлов.")
