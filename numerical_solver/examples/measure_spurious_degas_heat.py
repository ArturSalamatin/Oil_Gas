"""Ложная теплота дегазации в недонасыщенной зоне при продолжении с расширенной S_g; обзор Salimi, Wolf, Bruining 2012 (vault)."""

import sys
from pathlib import Path

import numpy as np

# example_runner подключает прототип radial_blackoil к sys.path —
# без него табличная PVT (пример 12) не строится.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import example_runner  # noqa: E402,F401

from gpn_multiphase_solver.factory import _create_pvt  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

# (конфиг, давления в недонасыщенной зоне p > p_b(R_s0), Па)
CASES = {
    "12 (таблицы)": (HERE / "12_large_drainage_radius" / "config.json",
                     [15.1e6, 15.3e6, 15.5e6]),
    "03 (Стендинг)": (HERE / "03_standing_corey" / "config.json",
                      [10e6, 12.5e6, 15e6, 17.5e6, 20e6]),
}
# Шаг центральной разности для dR_s,нас/dp, Па.
DP = 1e4


def main():
    for name, (cfg_path, pressures) in CASES.items():
        cfg = load_config(cfg_path)
        pvt = _create_pvt(cfg)
        rho_os, rho_gs = pvt.rho_o_std, pvt.rho_g_std
        Rs0 = cfg.initial_conditions.Rs0
        T0 = cfg.initial_conditions.T0
        pb = pvt.pb(np.array([Rs0]))[0]
        print(f"\n=== Пример {name}: R_s0 = {Rs0}, p_b(R_s0) = {pb / 1e6:.3f} МПа")
        print(f"{'p, МПа':>7} {'Rs_нас':>7} {'dRs/dp, 1/МПа':>14} {'Bo':>7} "
              f"{'Bo_нас/Bo':>9} {'Λ':>6} {'Tα':>6} {'Λ/Tα':>6} "
              f"{'μ_ложн, К/МПа':>14} {'μ_JT,o, К/МПа':>14} {'|μ_ложн/μ_JT,o|':>15}")
        for p in pressures:
            pa = np.array([p])
            Ta = np.array([T0])
            Rs_sat = pvt.Rs_eq(pa)[0]
            dRs_dp = (pvt.Rs_eq(np.array([p + DP]))[0]
                      - pvt.Rs_eq(np.array([p - DP]))[0]) / (2 * DP)
            # Истинное состояние: недонасыщенная нефть с R_s = R_s0.
            Bo = pvt.Bo(pa, np.array([Rs0]))[0]
            Bo_sat = pvt.Bo(pa, np.array([Rs_sat]))[0]
            rho_o = (rho_os + Rs0 * rho_gs) / Bo
            cp_o = pvt.c_p_oil(pa, Ta)[0]
            mu_jt_o = pvt.mu_JT_oil(pa, Ta)[0]
            L = pvt.L_degas(pa, Ta)[0]

            # Мнимая нефть несёт R_s,нас(p) и всю нефть ст: 1/Bo(p, R_s0) м³ст на м³ пор.
            # Ложный темп дегазации ṁ = −ρ_g,ст·φ/Bo·(dR_s,нас/dp)·ṗ, источник
            # Q_deg = −L·ṁ = φ·Λ·ṗ; при ṗ < 0 (падение давления) Q_deg < 0 — охлаждение.
            Lam = L * rho_gs * dRs_dp / Bo
            # Адиабатический член однофазной зоны Q_ad = φ·(1 + ρ_o c_p,o μ_JT,o)·ṗ = φ·Tα·ṗ.
            T_alpha = 1.0 + rho_o * cp_o * mu_jt_o
            # Конвективная часть ложного источника вдоль потока нефти эквивалентна
            # добавке к коэффициенту JT: μ_ложн = Λ/(ρ_o c_p,o) > 0 (охлаждение при
            # падении давления), физический μ_JT,o < 0 (нагрев).
            mu_false = Lam / (rho_o * cp_o)
            print(f"{p / 1e6:7.2f} {Rs_sat:7.2f} {dRs_dp * 1e6:14.3f} {Bo:7.4f} "
                  f"{Bo_sat / Bo:9.4f} {Lam:6.3f} {T_alpha:6.3f} {Lam / T_alpha:6.2f} "
                  f"{mu_false * 1e6:14.3f} {mu_jt_o * 1e6:14.3f} "
                  f"{abs(mu_false / mu_jt_o):15.2f}")


if __name__ == "__main__":
    main()
