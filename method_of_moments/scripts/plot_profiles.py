"""Визуализация параметризации профилей p(r), Sg(r), T(r) (FEAT-003).

Запуск:
    cd method_of_moments
    .venv/Scripts/python scripts/plot_profiles.py

Результаты сохраняются в results/profiles/*.png и *.svg.
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from profiles.pressure import PressureProfile
from profiles.saturation import SaturationProfile
from profiles.temperature import TemperatureProfile
from pvt.black_oil import BlackOilFluid

# ─── Параметры (baseline) ──────────────────────────────────────────────
R_W = 0.1       # м
R_EXT = 500.0   # м
P_WF = 15e6     # Па
P_0 = 20e6      # Па
P_B = 18e6      # Па
T_0 = 350.0     # К
R_B = 10.0      # м
SG_W = 0.15
BETA = 2.0
SIGMA = 2.0
DT_W = 5.0      # К

FLUID = BlackOilFluid({"rho_o_st": 850.0, "rho_g_st": 0.85}, P_B, T_0)

OUT_DIR = Path(__file__).resolve().parent.parent / "results" / "profiles"
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


# ═══ 1. p(r) — профиль давления ══════════════════════════════════════
def plot_pressure_profile():
    pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
    tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)
    pb_star = pp.pb_star(R_B, DT_W, FLUID, tp)
    gamma = pp.gamma(R_B, pb_star)

    r = np.geomspace(R_W, R_EXT, 500)
    p = np.array([pp(ri, R_B, pb_star, gamma) for ri in r])

    fig, ax = plt.subplots()
    ax.semilogx(r, p / 1e6)
    ax.axvline(R_B, color="k", ls="--", lw=0.8, label=f"$r_b$ = {R_B} м")
    ax.axhline(pb_star / 1e6, color="r", ls=":", lw=0.8,
               label=f"$p_b^*$ = {pb_star/1e6:.2f} МПа")
    ax.set_xlabel("$r$, м")
    ax.set_ylabel("$p$, МПа")
    ax.set_title(f"Профиль давления ($\\gamma$ = {gamma:.3f})")
    ax.legend()
    _save(fig, "pressure_profile")


# ═══ 2. dp/dr — производная давления ══════════════════════════════════
def plot_dp_dr():
    pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
    tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)
    pb_star = pp.pb_star(R_B, DT_W, FLUID, tp)
    gamma = pp.gamma(R_B, pb_star)

    r_inner = np.geomspace(R_W * 1.01, R_B, 200)
    r_outer = np.geomspace(R_B, R_EXT, 200)

    dp_inner = np.array([pp.dp_dr(ri, R_B, pb_star, gamma) for ri in r_inner])
    dp_outer = np.array([pp.dp_dr(ri, R_B, pb_star, gamma) for ri in r_outer])

    fig, ax = plt.subplots()
    ax.loglog(r_inner, dp_inner, label="внутренняя зона")
    ax.loglog(r_outer, dp_outer, label="внешняя зона")
    ax.axvline(R_B, color="k", ls="--", lw=0.8, label=f"$r_b$ = {R_B} м")
    ax.set_xlabel("$r$, м")
    ax.set_ylabel("$dp/dr$, Па/м")
    ax.set_title(f"Градиент давления ($\\gamma$ = {gamma:.3f})")
    ax.legend()
    _save(fig, "dp_dr")


# ═══ 3. Sg(r) — профиль газонасыщенности ═════════════════════════════
def plot_saturation_profile():
    fig, ax = plt.subplots()
    r = np.geomspace(R_W, R_EXT, 500)

    for beta in [1.0, 2.0, 5.0]:
        sp = SaturationProfile(R_W, beta=beta)
        Sg = np.array([sp(ri, R_B, SG_W) for ri in r])
        ax.semilogx(r, Sg, label=f"$\\beta$ = {beta}")

    ax.axvline(R_B, color="k", ls="--", lw=0.8, label=f"$r_b$ = {R_B} м")
    ax.set_xlabel("$r$, м")
    ax.set_ylabel("$S_g$")
    ax.set_title(f"Профиль газонасыщенности ($S_{{g,w}}$ = {SG_W})")
    ax.legend()
    _save(fig, "saturation_profile")


# ═══ 4. T(r) — профиль температуры ═══════════════════════════════════
def plot_temperature_profile():
    fig, ax = plt.subplots()
    r = np.geomspace(R_W, R_EXT, 500)

    for sigma in [0.5, 1.0, 2.0, 5.0]:
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=sigma)
        T = np.array([tp(ri, DT_W) for ri in r])
        ax.semilogx(r, T, label=f"$\\sigma$ = {sigma}")

    ax.axvline(R_B, color="k", ls="--", lw=0.8, label=f"$r_b$ = {R_B} м")
    ax.set_xlabel("$r$, м")
    ax.set_ylabel("$T$, К")
    ax.set_title(f"Профиль температуры ($\\Delta T_w$ = {DT_W} К)")
    ax.legend()
    _save(fig, "temperature_profile")


# ═══ 5. Ψ(ζ) — функция формы ═════════════════════════════════════════
def plot_Psi():
    zeta = np.linspace(0, 1, 300)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    for sigma in [0.5, 1.0, 2.0, 5.0]:
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=sigma)
        Psi = np.array([tp.Psi(z) for z in zeta])
        dPsi = np.array([tp.dPsi_dzeta(z) for z in zeta])
        ax1.plot(zeta, Psi, label=f"$\\sigma$ = {sigma}")
        ax2.plot(zeta, dPsi, label=f"$\\sigma$ = {sigma}")

    ax1.set_xlabel("$\\zeta$")
    ax1.set_ylabel("$\\Psi(\\zeta)$")
    ax1.set_title("Функция формы $\\Psi(\\zeta) = \\zeta^\\sigma(2 - \\zeta^\\sigma)$")
    ax1.legend()

    ax2.set_xlabel("$\\zeta$")
    ax2.set_ylabel("$\\Psi'(\\zeta)$")
    ax2.set_title("Производная $\\Psi'(\\zeta)$")
    ax2.legend()

    fig.tight_layout()
    _save(fig, "Psi_shape")


# ═══ 6. Φ(η) — функция формы давления ════════════════════════════════
def plot_Phi():
    eta = np.linspace(0, 1, 300)

    pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
    tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)
    pb_star = pp.pb_star(R_B, DT_W, FLUID, tp)
    gamma = pp.gamma(R_B, pb_star)

    fig, ax = plt.subplots()
    for g in [0.5, gamma, 1.0, 2.0]:
        Phi = eta ** g
        label = f"$\\gamma$ = {g:.3f}" if g == gamma else f"$\\gamma$ = {g}"
        ls = "-" if g == gamma else "--"
        lw = 2.0 if g == gamma else 1.2
        ax.plot(eta, Phi, ls=ls, lw=lw, label=label)

    ax.set_xlabel("$\\eta$")
    ax.set_ylabel("$\\Phi(\\eta)$")
    ax.set_title(f"Функция формы давления $\\Phi(\\eta) = \\eta^\\gamma$ (baseline $\\gamma$ = {gamma:.3f})")
    ax.legend()
    _save(fig, "Phi_shape")


# ═══ 7. Все профили на одном рисунке ═════════════════════════════════
def plot_combined():
    pp = PressureProfile(R_W, R_EXT, P_WF, P_0)
    sp = SaturationProfile(R_W, beta=BETA)
    tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=SIGMA)
    pb_star = pp.pb_star(R_B, DT_W, FLUID, tp)
    gamma = pp.gamma(R_B, pb_star)

    r = np.geomspace(R_W, R_EXT, 500)
    p = np.array([pp(ri, R_B, pb_star, gamma) for ri in r])
    Sg = np.array([sp(ri, R_B, SG_W) for ri in r])
    T = np.array([tp(ri, DT_W) for ri in r])

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 12), sharex=True)

    ax1.semilogx(r, p / 1e6, color="C0")
    ax1.axvline(R_B, color="k", ls="--", lw=0.8)
    ax1.axhline(pb_star / 1e6, color="r", ls=":", lw=0.8)
    ax1.set_ylabel("$p$, МПа")
    ax1.set_title("Профили p(r), $S_g$(r), T(r) — baseline")

    ax2.semilogx(r, Sg, color="C1")
    ax2.axvline(R_B, color="k", ls="--", lw=0.8)
    ax2.set_ylabel("$S_g$")

    ax3.semilogx(r, T, color="C2")
    ax3.axvline(R_B, color="k", ls="--", lw=0.8)
    ax3.set_xlabel("$r$, м")
    ax3.set_ylabel("$T$, К")

    fig.tight_layout()
    _save(fig, "combined_profiles")


# ═══ 8. J^(m) — интеграл ═════════════════════════════════════════════
def plot_J_integral():
    m_arr = np.arange(0, 10)
    fig, ax = plt.subplots()

    for sigma in [0.5, 1.0, 2.0, 5.0]:
        tp = TemperatureProfile(R_W, R_EXT, T_0, sigma=sigma)
        J_vals = [tp.J(m) for m in m_arr]
        ax.plot(m_arr, J_vals, "o-", label=f"$\\sigma$ = {sigma}")

    ax.set_xlabel("$m$")
    ax.set_ylabel("$J^{(m)}$")
    ax.set_title("Интеграл $J^{(m)} = 2/(m+1) - 1/(m+\\sigma+1)$")
    ax.legend()
    _save(fig, "J_integral")


# ═══ main ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Сохранение в {OUT_DIR}/")
    plot_pressure_profile()
    plot_dp_dr()
    plot_saturation_profile()
    plot_temperature_profile()
    plot_Psi()
    plot_Phi()
    plot_combined()
    plot_J_integral()
    print("Готово: 8 графиков x 2 формата (png + svg) = 16 файлов.")
