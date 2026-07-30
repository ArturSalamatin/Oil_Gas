"""Тесты коэффициентов ODE — §5 moments_method.tex."""

import json
import math
from pathlib import Path

import pytest

from src.pvt.black_oil import BlackOilFluid
from src.coefficients import frozen_pvt_zone1, frozen_pvt_zone2


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
