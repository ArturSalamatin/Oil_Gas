"""Тесты правой части ODE — FEAT-007a."""

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from src.pvt.black_oil import BlackOilFluid
from src.coefficients import OdeState, assemble_ode_system
from src.ode_system import make_rhs
from src.profiles.pressure import PressureProfile
from src.profiles.temperature import TemperatureProfile
from src.profiles.saturation import SaturationProfile


# ─── Фикстуры ─────────────────────────────────────────────────────

CONFIGS = Path(__file__).resolve().parent.parent / "configs"

P_WF = 15e6
R_W = 0.1
R_EXT = 500.0
SIGMA = 2.0
BETA = 2.0


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


@pytest.fixture
def p_profile():
    return PressureProfile(R_W, R_EXT, P_WF, 20e6)


@pytest.fixture
def t_profile():
    return TemperatureProfile(R_W, R_EXT, 350.0, SIGMA)


@pytest.fixture
def s_profile():
    return SaturationProfile(R_W, BETA)


@pytest.fixture
def rhs_func(fluid, rock, p_profile, t_profile, s_profile):
    return make_rhs(fluid, rock, p_profile, t_profile, s_profile, P_WF)


# ─── Baseline состояние ───────────────────────────────────────────

Y_BASELINE = np.array([5.0, 0.1, 2.0])


# ─── Тесты ─────────────────────────────────────────────────────────


class TestRhsBasic:
    def test_rhs_returns_ndarray(self, rhs_func):
        result = rhs_func(0, Y_BASELINE)
        assert isinstance(result, np.ndarray)
        assert result.shape == (3,)

    def test_rhs_all_finite(self, rhs_func):
        result = rhs_func(0, Y_BASELINE)
        assert np.all(np.isfinite(result)), f"ẋ содержит NaN/Inf: {result}"

    def test_rhs_dot_rb_positive(self, rhs_func):
        result = rhs_func(0, Y_BASELINE)
        assert result[0] > 0, (
            f"ṙ_b = {result[0]:.6e} должен быть > 0 (фронт разгазирования растёт)"
        )


class TestRhsConsistency:
    def test_rhs_matches_manual_solve(self, rhs_func, fluid, rock,
                                      p_profile, t_profile, s_profile):
        state = OdeState(r_b=5.0, Sg_w=0.1, dT_w=2.0, p_wf=P_WF)
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile,
                                   s_profile, state)
        expected = np.linalg.solve(A, F)
        result = rhs_func(0, Y_BASELINE)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    def test_rhs_pure_function(self, rhs_func):
        r1 = rhs_func(0, Y_BASELINE)
        r2 = rhs_func(0, Y_BASELINE)
        np.testing.assert_array_equal(r1, r2)


class TestRhsEdgeCases:
    def test_rhs_small_Sg(self, rhs_func):
        y = np.array([0.2, 0.01, 0.1])
        result = rhs_func(0, y)
        assert np.all(np.isfinite(result)), (
            f"ẋ при Sg≈0, rb≈rw содержит NaN/Inf: {result}"
        )


class TestRhsSolveIvp:
    def test_rhs_one_step_solve_ivp(self, rhs_func):
        sol = solve_ivp(
            rhs_func, (0, 1.0), Y_BASELINE,
            method="Radau", max_step=1.0, rtol=1e-6, atol=1e-9,
        )
        assert sol.success, f"solve_ivp не сошёлся: {sol.message}"
        assert np.all(np.isfinite(sol.y[:, -1])), (
            f"y_final содержит NaN/Inf: {sol.y[:, -1]}"
        )
        assert sol.y[0, -1] > Y_BASELINE[0], (
            f"rb не вырос: {sol.y[0, -1]:.6f} ≤ {Y_BASELINE[0]:.6f}"
        )
