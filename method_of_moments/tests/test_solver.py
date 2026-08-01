"""Тесты solver-обёртки — FEAT-007b."""

import json
from pathlib import Path

import numpy as np
import pytest

from src.pvt.black_oil import BlackOilFluid
from src.profiles.pressure import PressureProfile
from src.profiles.temperature import TemperatureProfile
from src.profiles.saturation import SaturationProfile
from src.solver import (
    _initial_conditions,
    _event_rb_reached,
    solve_moments,
    reconstruct_profiles,
)


# ─── Фикстуры ─────────────────────────────────────────────────────

CONFIGS = Path(__file__).resolve().parent.parent / "configs"

P_WF = 15e6
P_0 = 20e6
R_W = 0.1
R_EXT = 500.0
T_0 = 350.0
SIGMA = 2.0
BETA = 2.0
T_EPS = 1e-5


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
    return PressureProfile(R_W, R_EXT, P_WF, P_0)


@pytest.fixture
def t_profile():
    return TemperatureProfile(R_W, R_EXT, T_0, SIGMA)


@pytest.fixture
def s_profile():
    return SaturationProfile(R_W, BETA)


@pytest.fixture
def y0(fluid, rock, p_profile, t_profile):
    return _initial_conditions(fluid, rock, p_profile, t_profile, P_WF, T_EPS)


# ─── Тесты начальных условий ──────────────────────────────────────


class TestInitialConditions:
    def test_initial_rb_greater_than_rw(self, y0):
        assert y0[0] > R_W

    def test_initial_rb_close_to_rw(self, y0):
        delta_rel = (y0[0] - R_W) / R_W
        assert 0.001 < delta_rel < 1.0

    def test_initial_Sgw_in_01(self, y0):
        assert 0 < y0[1] < 1

    def test_initial_dTw_zero(self, y0):
        assert y0[2] == 0.0

    def test_initial_conditions_all_finite(self, y0):
        assert np.all(np.isfinite(y0))


# ─── Тесты event ──────────────────────────────────────────────────


class TestEvent:
    def test_event_positive_at_start(self, y0):
        event = _event_rb_reached(R_EXT)
        assert event(0, y0) > 0

    def test_event_zero_at_re(self):
        event = _event_rb_reached(500.0)
        y = np.array([500.0, 0.1, 2.0])
        assert event(0, y) == 0.0

    def test_event_terminal(self):
        event = _event_rb_reached(500.0)
        assert event.terminal is True
        assert event.direction == -1


# ─── Тесты solve_moments ──────────────────────────────────────────


@pytest.mark.filterwarnings("ignore::scipy.integrate.IntegrationWarning")
class TestSolveMoments:
    @pytest.fixture
    def sol(self, fluid, rock, p_profile, t_profile, s_profile):
        return solve_moments(
            fluid, rock, p_profile, t_profile, s_profile,
            P_WF, R_EXT, t_end=0.1, t_eps=T_EPS,
        )

    def test_solve_runs_without_crash(self, sol):
        assert sol.t.size >= 2

    def test_rb_monotonic(self, sol):
        if sol.t.size < 2:
            pytest.skip("Radau не сделал ни одного шага")
        assert np.all(np.diff(sol.y[0]) >= 0)

    def test_Sgw_in_bounds(self, sol):
        assert np.all(sol.y[1] >= 0)
        assert np.all(sol.y[1] <= 1)

    def test_dTw_nonnegative(self, sol):
        assert np.all(sol.y[2] >= -1e-12)

    def test_rb_stays_in_bounds(self, sol):
        assert np.all(sol.y[0] >= R_W)
        assert np.all(sol.y[0] <= R_EXT)

    def test_all_finite(self, sol):
        assert np.all(np.isfinite(sol.y))

    @pytest.mark.slow
    @pytest.mark.filterwarnings("ignore::scipy.integrate.IntegrationWarning")
    def test_solve_t10_no_nan(self, fluid, rock, p_profile, t_profile,
                              s_profile):
        """BUG-001: solver не должен падать при t_end=10 (gamma пересекает 0.5)."""
        sol = solve_moments(
            fluid, rock, p_profile, t_profile, s_profile,
            P_WF, R_EXT, t_end=10.0, t_eps=T_EPS,
        )
        assert sol.t.size >= 2
        assert np.all(np.isfinite(sol.y))


# ─── Тесты reconstruct_profiles ───────────────────────────────────


class TestReconstructProfiles:
    R_B = 5.0
    SG_W = 0.1
    DT_W = 2.0

    @pytest.fixture
    def r_grid(self):
        return np.linspace(R_W, R_EXT, 50)

    @pytest.fixture
    def profiles(self, p_profile, t_profile, s_profile, fluid, r_grid):
        return reconstruct_profiles(
            self.R_B, self.SG_W, self.DT_W,
            p_profile, t_profile, s_profile, fluid, r_grid,
        )

    def test_pressure_at_rw_equals_pwf(self, profiles):
        p_arr, _, _ = profiles
        np.testing.assert_allclose(p_arr[0], P_WF, rtol=1e-6)

    def test_pressure_at_Rext_equals_p0(self, profiles):
        p_arr, _, _ = profiles
        np.testing.assert_allclose(p_arr[-1], P_0, rtol=1e-6)

    def test_pressure_monotonic(self, profiles):
        p_arr, _, _ = profiles
        assert np.all(np.diff(p_arr) >= 0)

    def test_Sg_at_rw_equals_Sgw(self, profiles):
        _, Sg_arr, _ = profiles
        np.testing.assert_allclose(Sg_arr[0], self.SG_W, rtol=1e-6)

    def test_Sg_zero_outside_rb(self, profiles, r_grid):
        _, Sg_arr, _ = profiles
        mask = r_grid > self.R_B
        assert np.all(Sg_arr[mask] == 0.0)

    def test_T_at_rw(self, profiles):
        _, _, T_arr = profiles
        np.testing.assert_allclose(T_arr[0], 348.0, rtol=1e-6)

    def test_T_at_Rext(self, profiles):
        _, _, T_arr = profiles
        np.testing.assert_allclose(T_arr[-1], T_0, rtol=1e-6)

    def test_profiles_shape(self, profiles, r_grid):
        p_arr, Sg_arr, T_arr = profiles
        assert p_arr.shape == r_grid.shape
        assert Sg_arr.shape == r_grid.shape
        assert T_arr.shape == r_grid.shape
