"""Масштаб отрицательной S_g: вариант N прототипа (BUG-014) против согласованного продолжения, ур. (17), (18) Abadpour, Panfilov 2009."""

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

# (конфиг, давления для таблицы, R_s0 из конфига — для скачка плотности на p_b)
CASES = {
    "12 (таблицы)": (HERE / "12_large_drainage_radius" / "config.json",
                     [6e6, 10e6, 14e6, 14.94e6], 30.0),
    "03 (Стендинг)": (HERE / "03_standing_corey" / "config.json",
                      [5e6, 10e6, 15e6, 20e6], 50.0),
}
# Дефицит R_s недонасыщенной нефти относительно R_s,нас(p), м³ст/м³ст.
DELTA_RS = (0.1, 1.0, 5.0)


def sg_variant_n(dRs, Bo_sat, Bg):
    """S_g варианта N, дающая в запасах отношение газ/нефть R_s,нас − ΔR_s; вывод — Abadpour Panfilov 2009 (vault)."""
    # Запасы варианта N на единицу порового объёма (м³ст):
    #   нефть  (1 − S)/Bo_sat,  газ  R_s,нас(1 − S)/Bo_sat + S/Bg.
    # Отношение газ/нефть = R_s,нас + S·Bo_sat/(Bg(1 − S)) = R_s,нас − ΔR_s
    # ⇒ S/(1 − S) = −ΔR_s·Bg/Bo_sat.
    a = -dRs * Bg / Bo_sat
    return a / (1.0 + a)


def sg_consistent(Rs, Rs_sat, rho_os, rho_gs):
    """Расширенная S̃_g по массовой доле газового компонента, аналог ур. (18) Abadpour, Panfilov 2009."""
    # X — массовая доля газа ст в нефти; равновесный газ — чистый газ (X = 1).
    def X(r):
        return r * rho_gs / (rho_os + r * rho_gs)
    return (X(Rs) - X(Rs_sat)) / (1.0 - X(Rs_sat))


def main():
    for name, (cfg_path, pressures, Rs0) in CASES.items():
        pvt = _create_pvt(load_config(cfg_path))
        rho_os, rho_gs = pvt.rho_o_std, pvt.rho_g_std
        print(f"\n=== Пример {name}: rho_o,ст = {rho_os}, rho_g,ст = {rho_gs}")
        print(f"{'p, МПа':>7} {'Rs_нас':>7} {'Bo_нас':>7} {'Bg':>8} "
              f"{'rho_o':>6} {'rho_g':>6} {'rho_o/rho_g':>11} {'rho_g_мн':>8} | "
              + " | ".join(f"dRs={d}: S_N, S~, S_N/S~" for d in DELTA_RS))
        for p in pressures:
            pa = np.array([p])
            Rs_sat = pvt.Rs_eq(pa)[0]
            Bo_sat = pvt.Bo(pa, np.array([Rs_sat]))[0]
            Bg = pvt.Bg(pa)[0]
            # Плотности фаз в пласте, кг/м³: нефть несёт растворённый газ.
            rho_o = (rho_os + Rs_sat * rho_gs) / Bo_sat
            rho_g = rho_gs / Bg
            # Кажущаяся плотность растворённого газа (заметка Panfilov Panfilova 2014):
            # ρ_g,ст·ΔR_s / (Bo_нас − Bo(p, R_s,нас − ΔR_s)) при ΔR_s = 1.
            Bo_under = pvt.Bo(pa, np.array([Rs_sat - 1.0]))[0]
            rho_g_mn = rho_gs * 1.0 / (Bo_sat - Bo_under)
            cols = []
            for d in DELTA_RS:
                s_n = sg_variant_n(d, Bo_sat, Bg)
                s_c = sg_consistent(Rs_sat - d, Rs_sat, rho_os, rho_gs)
                cols.append(f"{s_n:.2e}, {s_c:.2e}, {s_n / s_c:.2f}")
            print(f"{p / 1e6:7.2f} {Rs_sat:7.2f} {Bo_sat:7.4f} {Bg:8.5f} "
                  f"{rho_o:6.1f} {rho_g:6.1f} {rho_o / rho_g:11.2f} {rho_g_mn:8.1f} | "
                  + " | ".join(cols))

        # ── Скачок плотности газа на давлении насыщения ──
        # Ячейка с R_s = R_s0 переходит между режимами при p = p_b(R_s0):
        # производная запасов газа по S̃_g скачет от ρ_g (двухфазная) к ρ_g,мн.
        pb = pvt.pb(np.array([Rs0]))[0]
        pa = np.array([pb])
        dBo = pvt.Bo(pa, np.array([Rs0]))[0] - pvt.Bo(pa, np.array([Rs0 - 1.0]))[0]
        rho_g_mn = rho_gs / dBo
        rho_g = rho_gs / pvt.Bg(pa)[0]
        print(f"  на p_b(Rs0={Rs0}) = {pb / 1e6:.3f} МПа: dBo/dRs = {dBo:.3e}, "
              f"rho_g_мн = {rho_g_mn:.1f}, rho_g = {rho_g:.1f}, "
              f"скачок = {rho_g_mn / rho_g:.2f}")


if __name__ == "__main__":
    main()
