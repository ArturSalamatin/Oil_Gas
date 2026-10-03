"""Согласованность PVT: сжимаемости нефти и газа неотрицательны (BUG-019).

A. Функции pvt/consistency.py: разности против аналитических производных
   формул Стендинга, граница нарушения у нефти конфига BUG-019, поиск интервалов.
B. Фабрика: предупреждение при отрицательной сжимаемости в диапазоне давлений
   задачи (как ECLIPSE «Negative Compressibility Found»); на согласованных
   конфигах проекта ложных предупреждений нет.
"""

import logging
import shutil
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import brentq

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.pvt.consistency import (
    gas_compressibility, negative_intervals,
    saturated_oil_compressibility, undersaturated_oil_compressibility,
)
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.units import (
    P_STD, PSI_TO_PA, RHO_AIR_STD, RHO_WATER_STD, SCF_PER_M3, T_STD,
)

SOLVER = Path(__file__).resolve().parent.parent          # numerical_solver
BUG019_CONFIG = Path(__file__).resolve().parent / "data" / "bug019_k10" / "config.json"
TABLE_DIR = SOLVER / "configs" / "table_pvt"
WARN_PREFIX = "PVT несогласована"

# PVT конфига BUG-019 — пример 20 до 2026-10-03 (FEAT-025): Стендинг,
# 800 кг/м³, γ_g = 1.014/1.225, T0 = 380 К, R_s0 = 500
RHO_O, RHO_G, T0, RS0 = 800.0, 1.014, 380.0, 500.0

# Таблица configs/table_pvt с B_o насыщенной нефти 1.40 вместо 1.20 на ветке
# R_s = 30 (p_b = 15 МПа): нефть «разбухает» быстрее, чем выделяется газ.
OIL_BAD = ("Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
           "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
           "30.0,15000000,1.40,0.0015\n30.0,30000000,1.38,0.0016\n")
# Газовая таблица с ростом B_g на 10–15 МПа (0.012 → 0.013)
GAS_BAD = ("pressure_Pa,Bg,mu_g_Pa_s\n"
           "5000000,0.020,0.000012\n10000000,0.012,0.000013\n"
           "15000000,0.013,0.000014\n30000000,0.004,0.000018\n")
# Таблица configs/table_pvt, где выше p_b ветки R_s = 30 B_o растёт с давлением
# (1.20 → 1.23 на 15–30 МПа вместо 1.20 → 1.18): недонасыщенная нефть «расширяется»
OIL_UNDER_BAD = ("Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
                 "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
                 "30.0,15000000,1.20,0.0015\n30.0,30000000,1.23,0.0016\n")


def _c_ot_standing_exact(p):
    """c_ot по аналитическим производным формул standing.py (co_undersaturated = 0)."""
    g_g = RHO_G / RHO_AIR_STD
    g_o = RHO_O / RHO_WATER_STD
    api = 141.5 / g_o - 131.5
    t_f = (T0 - 273.15) * 9.0 / 5.0 + 32.0
    a = 0.00091 * t_f - 0.0125 * api
    y = p / PSI_TO_PA / 18.2 + 1.4                      # standing.py:76
    rs = g_g * y ** (1 / 0.83) * 10.0 ** (-a / 0.83) / SCF_PER_M3
    drs = rs / 0.83 / (18.2 * y) / PSI_TO_PA
    f = rs * SCF_PER_M3 * (g_g / g_o) ** 0.5 + 1.25 * t_f   # standing.py:82-84
    bo = 0.9759 + 1.2e-4 * f ** 1.2
    dbo = 1.2e-4 * 1.2 * f ** 0.2 * SCF_PER_M3 * (g_g / g_o) ** 0.5 * drs
    bg = P_STD * T0 / (T_STD * p)                       # идеальный газ, standing.py:104-106
    return (bg * drs - dbo) / bo


@pytest.fixture(scope="module")
def pvt20():
    return StandingFullPVT(rho_o_std=RHO_O, rho_g_std=RHO_G, T0=T0, Rs0=RS0)


# ═══════════════════════════════════════════════════════════
# A. Функции pvt/consistency.py
# ═══════════════════════════════════════════════════════════

class TestCompressibilityFunctions:

    def test_c_ot_matches_standing_analytic(self, pvt20):
        # Центральная разность (шаг 1e-6·p) против аналитических производных
        # формул Стендинга. Замер плана: относительная разница ≤ 2e-9 на
        # 5–46 МПа; допуск 1e-6 ловит ошибку в самой формуле c_ot (знак,
        # B_o вместо B_g, производная при фиксированном R_s вместо полной).
        p = np.array([5e6, 10e6, 20e6, 30e6, 34e6, 40e6, 46e6])
        np.testing.assert_allclose(saturated_oil_compressibility(pvt20, p),
                                   _c_ot_standing_exact(p), rtol=1e-6)

    def test_c_ot_changes_sign_at_34_55_mpa(self, pvt20):
        # Причина BUG-019: у нефти конфига BUG-019 B_g·dR_s/dp < dB_o/dp выше
        # 34.55 МПа (R_s ≈ 351 м³/м³ при данных Стендинга до 1425 scf/STB ≈
        # 254 м³/м³). Корень по аналитике — 34.545689 МПа (замер плана).
        def c(q):
            return saturated_oil_compressibility(pvt20, np.array([q]))[0]
        assert c(30e6) > 0.0 and c(40e6) < 0.0
        assert brentq(c, 30e6, 40e6) == pytest.approx(34.5457e6, abs=1e3)

    def test_c_g_ideal_gas(self, pvt20):
        # B_g идеального газа ∝ 1/p, поэтому c_g = 1/p
        p = np.array([1e6, 10e6, 40e6])
        np.testing.assert_allclose(gas_compressibility(pvt20, p), 1.0 / p, rtol=1e-8)

    @pytest.mark.parametrize("co", [0.0, 5e-10])
    def test_c_o_undersaturated_standing(self, co):
        # Выше p_b Стендинг задаёт B_o = B_o(p_b)·exp(−co·(p − p_b)): c_o = co.
        # При co = 0 B_o от p не зависит — ровно 0 (граница допустимого, не
        # нарушение: проверка ищет c < 0 строго).
        pvt = StandingFullPVT(rho_o_std=RHO_O, rho_g_std=RHO_G, T0=T0, Rs0=100.0,
                              co_undersaturated=co)
        pb = float(pvt.pb(np.array([100.0]))[0])
        c_o = undersaturated_oil_compressibility(pvt, np.array([pb + 1e6, pb + 10e6]), 100.0)
        if co == 0.0:
            assert np.all(c_o == 0.0)
        else:
            np.testing.assert_allclose(c_o, co, rtol=1e-6)

    @pytest.mark.parametrize("func, expected", [
        (lambda p: p - 3.0, [(0.0, 3.0)]),                  # с нижней границы диапазона
        (lambda p: (p - 2.0) * (p - 5.0), [(2.0, 5.0)]),    # внутри диапазона
        (lambda p: p + 1.0, []),                            # нигде
        (lambda p: -1.0 - p, [(0.0, 10.0)]),                # на всём диапазоне
        (lambda p: (p - 2.0) * (p - 4.0) * (p - 6.0) * (p - 8.0),
         [(2.0, 4.0), (6.0, 8.0)]),                         # два интервала
    ], ids=["low_end", "interior", "none", "whole", "two"])
    def test_negative_intervals(self, func, expected):
        # 30 точек на [0, 10] (шаг 0.34); границы уточняются делением пополам
        # (40 раз): точность 0.34/2^40 — проверяем 1e-9
        got = negative_intervals(func, 0.0, 10.0)
        assert len(got) == len(expected)
        for (p1, p2, c_min), (e1, e2) in zip(got, expected):
            assert p1 == pytest.approx(e1, abs=1e-9)
            assert p2 == pytest.approx(e2, abs=1e-9)
            assert c_min < 0.0
