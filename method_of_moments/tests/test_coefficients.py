"""Тесты коэффициентов ODE — §5 moments_method.tex."""

import json
import math
from pathlib import Path

import pytest

from src.pvt.black_oil import BlackOilFluid
from src.coefficients import (
    frozen_pvt_zone1, frozen_pvt_zone2,
    dp_drb_numerical, dp_dpwf_numerical,
)
from src.profiles.pressure import PressureProfile
from src.profiles.temperature import TemperatureProfile


# ─── Фикстуры ─────────────────────────────────────────────────────

CONFIGS = Path(__file__).resolve().parent.parent / "configs"


@pytest.fixture
def baseline_config():
    with open(CONFIGS / "baseline.json") as f:
        return json.load(f)


@pytest.fixture
def fluid(baseline_config):
    cfg = baseline_config
    return BlackOilFluid(
        pvt_config=cfg["pvt"],
        p_b=cfg["initial_conditions"]["p_b"],
        T_0=cfg["initial_conditions"]["T_0"],
        relperm_config=cfg["relative_permeability"],
    )


@pytest.fixture
def rock(baseline_config):
    return baseline_config["rock"]


# ─── Параметры baseline ───────────────────────────────────────────

P_WF = 15e6
P_0 = 20e6
P_B = 18e6
T_0 = 350.0
SG_BASELINE = 0.1
PHI = 0.2
CR = 5e-10


# ─── Тесты Cp ─────────────────────────────────────────────────────

class TestCp:
    def test_Cp_positive(self, fluid):
        val = fluid.Cp(P_WF, T_0, SG_BASELINE, PHI, CR)
        assert val > 0, f"Cp должен быть > 0, получено {val}"

    def test_Cp_single_phase(self, fluid):
        val = fluid.Cp(P_0, T_0, 0.0, PHI, CR)
        assert val > 0, f"Cp (однофазный) должен быть > 0, получено {val}"

    def test_Cp_dimension(self, fluid):
        val = fluid.Cp(P_WF, T_0, SG_BASELINE, PHI, CR)
        assert 1e-12 < abs(val) < 1e-6, (
            f"Cp ~ 1e-10..1e-8 [1/Па], получено {val:.3e}"
        )


# ─── Тесты CT ─────────────────────────────────────────────────────

class TestCT:
    def test_CT_negative(self, fluid):
        val = fluid.CT(P_WF, T_0, SG_BASELINE, PHI)
        assert val < 0, f"CT должен быть < 0, получено {val}"

    def test_CT_single_phase(self, fluid):
        p_above_pb = P_0
        val = fluid.CT(p_above_pb, T_0, 0.0, PHI)
        Bo_val = fluid.Bo(p_above_pb, T_0)
        Bg_val = fluid.Bg(p_above_pb, T_0)
        beta_o_val = fluid.beta_o(p_above_pb, T_0)
        expected = -PHI * beta_o_val / Bg_val
        # При Sg=0, p>pb: CT = phi*(-beta_o*(1/Bg - Rs/Bo) + xi_o*(0 - Rs*beta_o) - 0)
        # = phi*(-beta_o/Bg + beta_o*Rs/Bo - Rs*beta_o/Bo) = -phi*beta_o/Bg
        assert val == pytest.approx(expected, rel=1e-10), (
            f"CT однофазный: {val:.6e} != -phi*beta_o/Bg = {expected:.6e}"
        )


# ─── Тесты замораживания PVT ──────────────────────────────────────

class TestFrozenPVT:
    def test_frozen_zone1_averages(self):
        pb_star = P_B
        p_bar, T_bar, Sg_bar = frozen_pvt_zone1(P_WF, pb_star, T_0, 5.0, SG_BASELINE)
        assert p_bar == pytest.approx(0.5 * (P_WF + pb_star))
        assert T_bar == pytest.approx(T_0 - 5.0)
        assert Sg_bar == pytest.approx(0.5 * SG_BASELINE)

    def test_frozen_zone2_Sg_zero(self):
        pb_star = P_B
        p_bar, T_bar, Sg_bar = frozen_pvt_zone2(pb_star, P_0, T_0)
        assert Sg_bar == 0.0
        assert p_bar == pytest.approx(0.5 * (pb_star + P_0))
        assert T_bar == pytest.approx(T_0)

    def test_frozen_zone1_isothermal(self):
        p_bar, T_bar, Sg_bar = frozen_pvt_zone1(P_WF, P_B, T_0, 0.0, SG_BASELINE)
        assert T_bar == pytest.approx(T_0)


# ─── Фикстуры профилей ────────────────────────────────────────────

R_W = 0.1
R_EXT = 500.0
SIGMA = 2.0


@pytest.fixture
def p_profile():
    return PressureProfile(R_W, R_EXT, P_WF, P_0)


@pytest.fixture
def t_profile():
    return TemperatureProfile(R_W, R_EXT, T_0, SIGMA)


# ─── Тесты dp/dr_b ────────────────────────────────────────────────

class TestDpDrb:
    def test_dp_drb_sign_inner(self, fluid, p_profile, t_profile):
        """∂p/∂r_b < 0 в зоне разгазирования."""
        r_b = 5.0
        dT_w = 2.0
        r_test = math.sqrt(R_W * r_b)
        val = dp_drb_numerical(p_profile, r_test, r_b, fluid, t_profile, dT_w)
        assert val < 0, f"∂p/∂r_b должен быть < 0 в зоне 1, получено {val:.6e}"

    def test_dp_drb_sign_outer(self, fluid, p_profile, t_profile):
        """∂p/∂r_b < 0 в однофазной зоне (или ≈0 вблизи контура)."""
        r_b = 5.0
        dT_w = 2.0
        r_test = math.sqrt(r_b * R_EXT)
        val = dp_drb_numerical(p_profile, r_test, r_b, fluid, t_profile, dT_w)
        assert val <= 0, f"∂p/∂r_b должен быть ≤ 0 в зоне 2, получено {val:.6e}"

    def test_dp_drb_zero_at_Rext(self, fluid, p_profile, t_profile):
        """∂p/∂r_b = 0 на контуре (p(R_ext) = p_0 = const)."""
        r_b = 5.0
        dT_w = 2.0
        val = dp_drb_numerical(p_profile, R_EXT, r_b, fluid, t_profile, dT_w)
        assert abs(val) < 1.0, f"∂p/∂r_b на контуре ≈ 0, получено {val:.6e}"

    def test_dp_drb_continuity_at_rb(self, fluid, p_profile, t_profile):
        """∂p/∂r_b непрерывна в r = r_b (конечная разность)."""
        r_b = 5.0
        dT_w = 2.0
        eps = 1e-4
        val_left = dp_drb_numerical(
            p_profile, r_b * (1 - eps), r_b, fluid, t_profile, dT_w)
        val_right = dp_drb_numerical(
            p_profile, r_b * (1 + eps), r_b, fluid, t_profile, dT_w)
        assert val_left == pytest.approx(val_right, rel=0.05), (
            f"Разрыв dp/dr_b на r_b: left={val_left:.6e}, right={val_right:.6e}"
        )


class TestDpDpwf:
    def test_dp_dpwf_at_rw(self, fluid, p_profile, t_profile):
        """∂p/∂p_wf(r_w) ≈ 1."""
        r_b = 5.0
        dT_w = 2.0
        val = dp_dpwf_numerical(p_profile, R_W, r_b, fluid, t_profile, dT_w)
        assert val == pytest.approx(1.0, abs=0.05), (
            f"∂p/∂p_wf(r_w) ≈ 1, получено {val:.6f}"
        )

    def test_dp_dpwf_at_Rext(self, fluid, p_profile, t_profile):
        """∂p/∂p_wf(R_ext) = 0 (p₀ = const)."""
        r_b = 5.0
        dT_w = 2.0
        val = dp_dpwf_numerical(p_profile, R_EXT, r_b, fluid, t_profile, dT_w)
        assert abs(val) < 1e-4, f"∂p/∂p_wf(R_ext) ≈ 0, получено {val:.6e}"

    def test_dp_dpwf_zero_in_zone2(self, fluid, p_profile, t_profile):
        """∂p/∂p_wf = 0 в однофазной зоне."""
        r_b = 5.0
        dT_w = 2.0
        r_test = math.sqrt(r_b * R_EXT)
        val = dp_dpwf_numerical(p_profile, r_test, r_b, fluid, t_profile, dT_w)
        assert abs(val) < 0.01, f"∂p/∂p_wf в зоне 2 ≈ 0, получено {val:.6e}"
