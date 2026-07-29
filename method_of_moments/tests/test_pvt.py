"""Тесты PVT-корреляций Black Oil (FEAT-001)."""

import json
import math
import pytest
from pathlib import Path

from src.pvt import correlations as cor
from src.pvt.black_oil import BlackOilFluid

# ─── Baseline параметры ────────────────────────────────────────────────
P = 15e6       # Па
P_B = 18e6     # Па
T = 350.0      # К
RHO_O_ST = 850.0
RHO_G_ST = 0.85

RS = cor.Rs(P, T, RHO_O_ST, RHO_G_ST)


# ═══ Rs, pb ════════════════════════════════════════════════════════════
class TestRs:
    def test_Rs_at_pb(self):
        """Roundtrip: pb(Rs(pb, T), T) ≈ pb."""
        Rs_at_pb = cor.Rs(P_B, T, RHO_O_ST, RHO_G_ST)
        pb_back = cor.pb(Rs_at_pb, T, RHO_O_ST, RHO_G_ST)
        assert abs(pb_back - P_B) < 100.0  # Па

    def test_Rs_above_pb(self):
        Rs_above = cor.Rs(25e6, T, RHO_O_ST, RHO_G_ST)
        Rs_at_pb = cor.Rs(P_B, T, RHO_O_ST, RHO_G_ST)
        # Standing: Rs растёт с p, при p > pb нужна обрезка в BlackOilFluid
        assert Rs_above >= Rs_at_pb

    def test_Rs_positive(self):
        assert cor.Rs(1e6, T, RHO_O_ST, RHO_G_ST) > 0

    def test_pb_roundtrip(self):
        """pb(Rs(p, T), T) ≈ p при p < pb."""
        Rs_val = cor.Rs(P, T, RHO_O_ST, RHO_G_ST)
        pb_back = cor.pb(Rs_val, T, RHO_O_ST, RHO_G_ST)
        assert abs(pb_back - P) < 1.0  # Па


# ═══ dRs/dp, dRs/dT ═══════════════════════════════════════════════════
class TestDRs:
    def test_dRs_dp_vs_finite_diff(self):
        dp = 100.0
        analytic = cor.dRs_dp(P, T, RHO_O_ST, RHO_G_ST)
        fd = (cor.Rs(P + dp, T, RHO_O_ST, RHO_G_ST)
              - cor.Rs(P - dp, T, RHO_O_ST, RHO_G_ST)) / (2 * dp)
        assert abs(analytic - fd) / abs(analytic) < 1e-6

    def test_dRs_dT_vs_finite_diff(self):
        dT = 0.01
        analytic = cor.dRs_dT(P, T, RHO_O_ST, RHO_G_ST)
        fd = (cor.Rs(P, T + dT, RHO_O_ST, RHO_G_ST)
              - cor.Rs(P, T - dT, RHO_O_ST, RHO_G_ST)) / (2 * dT)
        assert abs(analytic - fd) / abs(analytic) < 1e-6

    def test_dRs_dT_negative(self):
        assert cor.dRs_dT(P, T, RHO_O_ST, RHO_G_ST) < 0

    def test_dRs_dp_zero_above_pb(self):
        fluid = BlackOilFluid({"rho_o_st": RHO_O_ST, "rho_g_st": RHO_G_ST},
                              P_B, T)
        assert fluid.dRs_dp(25e6, T) == 0.0


# ═══ Bo ════════════════════════════════════════════════════════════════
class TestBo:
    def test_Bo_greater_than_one(self):
        assert cor.Bo(P, T, RS, RHO_O_ST, RHO_G_ST) > 1.0

    def test_Bo_increases_with_Rs(self):
        Rs1 = 50.0
        Rs2 = 200.0
        assert cor.Bo(P, T, Rs1, RHO_O_ST, RHO_G_ST) < \
               cor.Bo(P, T, Rs2, RHO_O_ST, RHO_G_ST)

    def test_dBo_dRs_vs_finite_diff(self):
        dRs = 0.01
        analytic = cor.dBo_dRs(P, T, RS, RHO_O_ST, RHO_G_ST)
        fd = (cor.Bo(P, T, RS + dRs, RHO_O_ST, RHO_G_ST)
              - cor.Bo(P, T, RS - dRs, RHO_O_ST, RHO_G_ST)) / (2 * dRs)
        assert abs(analytic - fd) / abs(analytic) < 1e-6

    def test_dBo_dT_vs_finite_diff(self):
        dT = 0.01
        analytic = cor.dBo_dT_fixed_Rs(P, T, RS, RHO_O_ST, RHO_G_ST)
        fd = (cor.Bo(P, T + dT, RS, RHO_O_ST, RHO_G_ST)
              - cor.Bo(P, T - dT, RS, RHO_O_ST, RHO_G_ST)) / (2 * dT)
        assert abs(analytic - fd) / abs(analytic) < 1e-5


# ═══ Bg ════════════════════════════════════════════════════════════════
class TestBg:
    def test_Bg_positive(self):
        assert cor.Bg(P, T) > 0

    def test_Bg_decreases_with_p(self):
        assert cor.Bg(10e6, T) > cor.Bg(20e6, T)

    def test_dBg_dp_vs_finite_diff(self):
        dp = 100.0
        analytic = cor.dBg_dp(P, T)
        fd = (cor.Bg(P + dp, T) - cor.Bg(P - dp, T)) / (2 * dp)
        assert abs(analytic - fd) / abs(analytic) < 1e-6

    def test_dBg_dT_vs_finite_diff(self):
        dT = 0.01
        analytic = cor.dBg_dT(P, T)
        fd = (cor.Bg(P, T + dT) - cor.Bg(P, T - dT)) / (2 * dT)
        assert abs(analytic - fd) / abs(analytic) < 1e-6


# ═══ Вязкости ══════════════════════════════════════════════════════════
class TestViscosity:
    def test_mu_o_positive(self):
        val = cor.mu_o(T, RS, RHO_O_ST)
        assert 1e-4 < val < 1e-1  # Па·с

    def test_mu_g_positive(self):
        val = cor.mu_g(P, T, RHO_G_ST)
        assert 1e-5 < val < 1e-4

    def test_mu_o_less_than_dead(self):
        assert cor.mu_o(T, RS, RHO_O_ST) < cor.mu_dead_oil(T, RHO_O_ST)

    def test_mu_od_beggs_robinson(self):
        """μ_od при baseline: порядок 1–10 cP."""
        val = cor.mu_dead_oil(T, RHO_O_ST)
        assert 1e-3 < val < 1e-2  # Па·с = 1..10 cP


# ═══ BlackOilFluid ═════════════════════════════════════════════════════
class TestBlackOilFluid:
    @pytest.fixture
    def fluid(self):
        return BlackOilFluid(
            {"rho_o_st": RHO_O_ST, "rho_g_st": RHO_G_ST}, P_B, T)

    def test_rho_o_formula(self, fluid):
        Rs_val = fluid.Rs(P, T)
        Bo_val = fluid.Bo(P, T)
        expected = (RHO_O_ST + Rs_val * RHO_G_ST) / Bo_val
        assert fluid.rho_o(P, T) == pytest.approx(expected, rel=1e-12)

    def test_rho_g_formula(self, fluid):
        expected = RHO_G_ST / cor.Bg(P, T)
        assert fluid.rho_g(P, T) == pytest.approx(expected, rel=1e-12)

    def test_co_sat_negative(self, fluid):
        # co = 0 для Standing, dBo/dRs > 0, dRs/dp > 0 → co_sat < 0
        assert fluid.co_sat(P, T) < fluid.co(P, T)

    def test_xi_o_range(self, fluid):
        Sg = 0.1
        val = fluid.xi_o(P, T, Sg)
        assert 0 < val < 1.0 / fluid.Bo(P, T)

    def test_alpha_o_equals_beta_o(self, fluid):
        assert fluid.alpha_o(P, T) == pytest.approx(
            fluid.beta_o(P, T), rel=1e-12)

    def test_cg_equals_1_over_p(self, fluid):
        assert fluid.cg(P, T) == pytest.approx(1.0 / P, rel=1e-12)

    def test_beta_o_vs_finite_diff(self, fluid):
        dT = 0.01
        Rs_val = fluid.Rs(P, T)
        Bo_m = cor.Bo(P, T - dT, Rs_val, RHO_O_ST, RHO_G_ST)
        Bo_p = cor.Bo(P, T + dT, Rs_val, RHO_O_ST, RHO_G_ST)
        Bo_0 = cor.Bo(P, T, Rs_val, RHO_O_ST, RHO_G_ST)
        fd = (Bo_p - Bo_m) / (2 * dT) / Bo_0
        assert fluid.beta_o(P, T) == pytest.approx(fd, rel=1e-5)

    def test_co_zero_standing(self, fluid):
        assert fluid.co(P, T) == 0.0

    def test_beta_o_sat_sign(self, fluid):
        # dBo/dRs > 0, dRs/dT < 0 → second term < 0 → beta_o_sat < beta_o
        assert fluid.beta_o_sat(P, T) < fluid.beta_o(P, T)

    def test_baseline_config_loads(self):
        config_path = Path(__file__).parent.parent / "configs" / "baseline.json"
        with open(config_path) as f:
            config = json.load(f)
        fluid = BlackOilFluid(
            config["pvt"],
            config["initial_conditions"]["p_b"],
            config["initial_conditions"]["T_0"])
        assert fluid.Rs_total > 0
        assert fluid.Bo(P, T) > 1.0
        assert fluid.mu_o(P, T) > 0
        assert fluid.mu_g(P, T) > 0


# ═══ Import test ═══════════════════════════════════════════════════════
def test_import():
    from src.pvt import BlackOilFluid, correlations
    assert callable(getattr(correlations, 'Rs', None))
    assert callable(BlackOilFluid)
