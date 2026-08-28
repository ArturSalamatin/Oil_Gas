"""Тесты для PVT (фаза 2).

Тесты воспроизводят формулы корреляций и сравнивают с результатами кода.
"""

import numpy as np
import pytest
from gpn_multiphase_solver.pvt import HydroPVT, FullPVT, StandingFullPVT
from gpn_multiphase_solver.units import (
    PA_TO_PSI, PSI_TO_PA, SCF_PER_M3,
    RHO_WATER_STD, RHO_AIR_STD, P_STD, T_STD,
)

RHO_O_STD = 800.0
RHO_G_STD = 0.78
T0 = 300.0
RS0 = 50.0
CO_UNDER = 5e-10

# Вспомогательные: промежуточные величины для эталонов
GAMMA_O = RHO_O_STD / RHO_WATER_STD
GAMMA_G = RHO_G_STD / RHO_AIR_STD
GAMMA_API = 141.5 / GAMMA_O - 131.5
T_F = (T0 - 273.15) * 9.0 / 5.0 + 32.0
A_STANDING = 0.00091 * T_F - 0.0125 * GAMMA_API


@pytest.fixture
def pvt():
    return StandingFullPVT(
        rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD, T0=T0, Rs0=RS0,
        co_undersaturated=CO_UNDER,
        c_p_oil=1880.0, c_p_gas=2800.0,
        mu_JT_oil_val=4e-7, mu_JT_gas_val=-4e-6, L_degas_val=168000.0,
    )


# ── ABC ───────────────────────────────────────────────────────

class TestABC:
    def test_isinstance_hydro(self, pvt):
        assert isinstance(pvt, HydroPVT)

    def test_isinstance_full(self, pvt):
        assert isinstance(pvt, FullPVT)

    def test_cannot_instantiate_hydro(self):
        with pytest.raises(TypeError):
            HydroPVT()

    def test_cannot_instantiate_full(self):
        with pytest.raises(TypeError):
            FullPVT()

    def test_rho_o_std(self, pvt):
        assert pvt.rho_o_std == RHO_O_STD

    def test_rho_g_std(self, pvt):
        assert pvt.rho_g_std == RHO_G_STD


# ── Rs_eq: воспроизведение формулы Standing ───────────────────

class TestRsEq:
    @pytest.mark.parametrize("p_pa", [1e6, 3e6, 5e6, 10e6, 20e6])
    def test_Rs_eq_formula(self, pvt, p_pa):
        """Воспроизведение формулы Standing 1947 для Rs."""
        p_psia = p_pa * PA_TO_PSI
        Y = p_psia / 18.2 + 1.4
        Rs_scf = GAMMA_G * Y ** (1.0 / 0.83) * 10.0 ** (-A_STANDING / 0.83)
        Rs_expected = Rs_scf / SCF_PER_M3

        Rs_code = pvt.Rs_eq(np.array([p_pa]))[0]
        assert Rs_code == pytest.approx(Rs_expected, rel=1e-12)

    def test_Rs_monotonic(self, pvt):
        p = np.linspace(1e6, 30e6, 50)
        assert np.all(np.diff(pvt.Rs_eq(p)) > 0)

    def test_Rs_vectorized(self, pvt):
        p = np.array([5e6, 10e6, 20e6])
        Rs = pvt.Rs_eq(p)
        assert Rs.shape == (3,)
        for i, pi in enumerate(p):
            assert Rs[i] == pytest.approx(pvt.Rs_eq(np.array([pi]))[0])


# ── pb: обратная к Rs_eq ──────────────────────────────────────

class TestPb:
    @pytest.mark.parametrize("Rs", [10.0, 30.0, 50.0, 80.0])
    def test_pb_formula(self, pvt, Rs):
        """Воспроизведение формулы Standing для pb."""
        Rs_scf = Rs * SCF_PER_M3
        pb_psia = 18.2 * ((Rs_scf / GAMMA_G) ** 0.83 * 10.0 ** A_STANDING - 1.4)
        pb_expected = pb_psia * PSI_TO_PA

        pb_code = pvt.pb(np.array([Rs]))[0]
        assert pb_code == pytest.approx(pb_expected, rel=1e-12)

    def test_pb_increases_with_Rs(self, pvt):
        Rs = np.array([10.0, 30.0, 60.0])
        pb_vals = pvt.pb(Rs)
        assert np.all(np.diff(pb_vals) > 0)

    def test_Rs_eq_pb_inverse(self, pvt):
        """Rs_eq и pb — взаимно обратные: Rs_eq(pb(Rs)) ≈ Rs."""
        Rs_vals = np.array([10.0, 30.0, 50.0])
        pb_vals = pvt.pb(Rs_vals)
        Rs_back = pvt.Rs_eq(pb_vals)
        np.testing.assert_allclose(Rs_back, Rs_vals, rtol=1e-10)


# ── Bo: Standing ниже pb, exp-сжимаемость выше pb ─────────────

class TestBo:
    def _Bo_standing(self, Rs):
        """Формула Standing для Bo (не зависит от p)."""
        Rs_scf = np.asarray(Rs, float) * SCF_PER_M3
        F = Rs_scf * (GAMMA_G / GAMMA_O) ** 0.5 + 1.25 * T_F
        return 0.9759 + 1.2e-4 * F ** 1.2

    @pytest.mark.parametrize("Rs", [10.0, 30.0, 50.0])
    def test_Bo_below_pb_formula(self, pvt, Rs):
        """Ниже pb(Rs): Bo = Standing(Rs). Rs=0 исключён (pb<0)."""
        pb_val = pvt.pb(np.array([Rs]))[0]
        assert pb_val > 0, f"pb({Rs}) = {pb_val} — должно быть > 0 для этого теста"
        p = pb_val * 0.5
        Bo_expected = self._Bo_standing(Rs)
        Bo_code = pvt.Bo(np.array([p]), np.array([Rs]))[0]
        assert Bo_code == pytest.approx(Bo_expected, rel=1e-12)

    def test_Bo_above_pb_exp_compressibility(self, pvt):
        """Выше pb(Rs): Bo = Bo_at_pb · exp(-co·(p-pb))."""
        Rs = np.array([50.0])
        pb_val = pvt.pb(Rs)[0]
        Bo_at_pb = self._Bo_standing(50.0)
        p_above = pb_val + 5e6
        Bo_expected = Bo_at_pb * np.exp(-CO_UNDER * (p_above - pb_val))
        Bo_code = pvt.Bo(np.array([p_above]), Rs)[0]
        assert Bo_code == pytest.approx(Bo_expected, rel=1e-10)

    def test_Bo_continuous_at_pb(self, pvt):
        """Непрерывность Bo на границе pb."""
        Rs = np.array([50.0])
        pb_val = pvt.pb(Rs)[0]
        eps = 10.0
        Bo_below = pvt.Bo(np.array([pb_val - eps]), Rs)[0]
        Bo_above = pvt.Bo(np.array([pb_val + eps]), Rs)[0]
        assert Bo_below == pytest.approx(Bo_above, rel=1e-6)

    def test_Bo_mixed_cells(self, pvt):
        """Массив с ячейками по обе стороны pb."""
        Rs = np.array([50.0, 50.0, 20.0, 20.0])
        pb_50 = pvt.pb(np.array([50.0]))[0]
        pb_20 = pvt.pb(np.array([20.0]))[0]
        p = np.array([pb_50 * 0.5, pb_50 * 1.5, pb_20 * 0.5, pb_20 * 1.5])

        Bo = pvt.Bo(p, Rs)
        assert Bo.shape == (4,)
        # Ячейки 0, 2: ниже pb → Standing
        assert Bo[0] == pytest.approx(self._Bo_standing(50.0), rel=1e-10)
        assert Bo[2] == pytest.approx(self._Bo_standing(20.0), rel=1e-10)
        # Ячейки 1, 3: выше pb → exp-сжимаемость, Bo < Bo_at_pb
        assert Bo[1] < self._Bo_standing(50.0)
        assert Bo[3] < self._Bo_standing(20.0)

    def test_Bo_increases_with_Rs_below_pb(self, pvt):
        Rs = np.array([0.0, 20.0, 50.0])
        p = np.full(3, 2e6)  # ниже pb для всех Rs
        Bo = pvt.Bo(p, Rs)
        assert Bo[1] > Bo[0]
        assert Bo[2] > Bo[1]

    def test_Bo_near_one_at_zero_Rs(self, pvt):
        Bo = pvt.Bo(np.array([2e6]), np.array([0.0]))[0]
        assert 0.95 < Bo < 1.1


# ── Bg: идеальный газ ─────────────────────────────────────────

class TestBg:
    @pytest.mark.parametrize("p_pa", [1e6, 5e6, 10e6, 20e6])
    def test_Bg_formula(self, pvt, p_pa):
        """Bg = P_std·T0 / (T_std·p)."""
        expected = P_STD * T0 / (T_STD * p_pa)
        assert pvt.Bg(np.array([p_pa]))[0] == pytest.approx(expected, rel=1e-14)

    def test_Bg_decreases_with_p(self, pvt):
        p = np.array([5e6, 10e6, 20e6])
        Bg = pvt.Bg(p)
        assert np.all(np.diff(Bg) < 0)


# ── mu_o: Beggs-Robinson ──────────────────────────────────────

class TestMuO:
    def test_mu_dead_oil_formula(self, pvt):
        """Воспроизведение Beggs-Robinson для dead oil."""
        Y = 3.0324 - 0.02023 * GAMMA_API
        A = 10.0 ** Y
        mu_od_cP = 10.0 ** (A * T_F ** (-1.163)) - 1.0
        mu_od_Pa_s = mu_od_cP * 1e-3
        # mu_o при Rs=0 = dead oil viscosity (A·mu_od^B с Rs_scf=0)
        Rs_scf = 0.0
        A_br = 10.715 / (Rs_scf + 100.0) ** 0.515
        B_br = 5.44 / (Rs_scf + 150.0) ** 0.338
        mu_expected = A_br * (mu_od_cP) ** B_br * 1e-3

        mu_code = pvt.mu_o(np.array([2e6]), np.array([0.0]))[0]
        assert mu_code == pytest.approx(mu_expected, rel=1e-10)

    @pytest.mark.parametrize("Rs", [0.0, 10.0, 30.0, 50.0])
    def test_mu_o_below_pb_formula(self, pvt, Rs):
        """Ниже pb: mu_o = Beggs-Robinson(Rs)."""
        pb_val = pvt.pb(np.array([Rs]))[0]
        p = max(pb_val * 0.5, 1e5)
        Rs_scf = Rs * SCF_PER_M3
        A_br = 10.715 / (Rs_scf + 100.0) ** 0.515
        B_br = 5.44 / (Rs_scf + 150.0) ** 0.338
        Y = 3.0324 - 0.02023 * GAMMA_API
        A_dead = 10.0 ** Y
        mu_od_cP = 10.0 ** (A_dead * T_F ** (-1.163)) - 1.0
        mu_expected = A_br * mu_od_cP ** B_br * 1e-3

        mu_code = pvt.mu_o(np.array([p]), np.array([Rs]))[0]
        assert mu_code == pytest.approx(mu_expected, rel=1e-10)

    def test_mu_o_decreases_with_Rs(self, pvt):
        Rs = np.array([0.0, 20.0, 50.0])
        p = np.full(3, 2e6)
        mu = pvt.mu_o(p, Rs)
        assert mu[1] < mu[0]
        assert mu[2] < mu[1]

    def test_mu_o_order_of_magnitude(self, pvt):
        mu = pvt.mu_o(np.array([5e6]), np.array([30.0]))[0]
        assert 1e-4 < mu < 0.1


# ── mu_g: Lee-Gonzalez-Eakin ──────────────────────────────────

class TestMuG:
    @pytest.mark.parametrize("p_pa", [5e6, 10e6, 20e6])
    def test_mu_g_formula(self, pvt, p_pa):
        """Воспроизведение формулы LGE."""
        M_g = 28.97 * GAMMA_G
        T_R = T0 * 9.0 / 5.0
        K = (9.4 + 0.02 * M_g) * T_R ** 1.5 / (209.0 + 19.0 * M_g + T_R)
        X = 3.5 + 986.0 / T_R + 0.01 * M_g
        Y_exp = 2.4 - 0.2 * X
        Bg = P_STD * T0 / (T_STD * p_pa)
        rho_g_gcc = (RHO_G_STD / Bg) / 1000.0
        mu_expected = 1e-4 * K * np.exp(X * rho_g_gcc ** Y_exp) * 1e-3

        mu_code = pvt.mu_g(np.array([p_pa]))[0]
        assert mu_code == pytest.approx(mu_expected, rel=1e-10)

    def test_mu_g_positive(self, pvt):
        assert pvt.mu_g(np.array([10e6]))[0] > 0

    def test_mu_g_order_of_magnitude(self, pvt):
        mu = pvt.mu_g(np.array([10e6]))[0]
        assert 1e-6 < mu < 1e-4


# ── rho: формула через Bo, Bg ─────────────────────────────────

class TestRho:
    @pytest.mark.parametrize("p_pa,Rs", [(5e6, 20.0), (10e6, 50.0)])
    def test_rho_o_formula(self, pvt, p_pa, Rs):
        """rho_o = (rho_o_std + Rs·rho_g_std) / Bo."""
        p = np.array([p_pa])
        Rs_arr = np.array([Rs])
        Bo = pvt.Bo(p, Rs_arr)[0]
        expected = (RHO_O_STD + Rs * RHO_G_STD) / Bo
        assert pvt.rho_o(p, Rs_arr)[0] == pytest.approx(expected, rel=1e-14)

    @pytest.mark.parametrize("p_pa", [5e6, 10e6, 20e6])
    def test_rho_g_formula(self, pvt, p_pa):
        """rho_g = rho_g_std / Bg."""
        p = np.array([p_pa])
        Bg = pvt.Bg(p)[0]
        expected = RHO_G_STD / Bg
        assert pvt.rho_g(p)[0] == pytest.approx(expected, rel=1e-14)

    def test_rho_o_gt_rho_g(self, pvt):
        p = np.array([10e6])
        assert pvt.rho_o(p, np.array([20.0]))[0] > pvt.rho_g(p)[0]


# ── Тепловые свойства (скалярные) ─────────────────────────────

class TestThermal:
    def test_c_p_oil(self, pvt):
        np.testing.assert_allclose(
            pvt.c_p_oil(np.array([5e6, 15e6]), np.array([300.0, 350.0])),
            1880.0)

    def test_c_p_gas(self, pvt):
        np.testing.assert_allclose(
            pvt.c_p_gas(np.array([10e6]), np.array([300.0])),
            2800.0)

    def test_mu_JT_oil(self, pvt):
        np.testing.assert_allclose(
            pvt.mu_JT_oil(np.array([10e6]), np.array([300.0])),
            4e-7)

    def test_mu_JT_gas(self, pvt):
        np.testing.assert_allclose(
            pvt.mu_JT_gas(np.array([10e6]), np.array([300.0])),
            -4e-6)

    def test_L_degas(self, pvt):
        np.testing.assert_allclose(
            pvt.L_degas(np.array([10e6]), np.array([300.0])),
            168000.0)

    def test_thermal_shape(self, pvt):
        p = np.array([5e6, 10e6, 15e6])
        T = np.array([290.0, 300.0, 310.0])
        assert pvt.c_p_oil(p, T).shape == (3,)
        assert pvt.mu_JT_gas(p, T).shape == (3,)
        assert pvt.L_degas(p, T).shape == (3,)
