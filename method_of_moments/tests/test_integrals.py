"""Тесты аналитических интегралов — FEAT-004."""

import pytest
from scipy.integrate import quad

from src.integrals import I_Phi, I_S, J

TOLERANCE = 1e-10

GAMMA_VALUES = [0.5, 1.0, 2.0, 5.0]
BETA_VALUES = [1.0, 2.0, 3.0]
SIGMA_VALUES = [0.5, 1.0, 2.0]
N_VALUES = [0, 1, 2, 3]
M_VALUES = [0, 1, 2, 3]


class TestIPhiQuad:
    """I_Φ^(n) vs scipy.integrate.quad."""

    @pytest.mark.parametrize("n", N_VALUES)
    @pytest.mark.parametrize("gamma", GAMMA_VALUES)
    def test_vs_quad(self, n, gamma):
        expected, _ = quad(lambda eta: eta ** (n * gamma), 0, 1)
        assert abs(I_Phi(n, gamma) - expected) < TOLERANCE


class TestISQuad:
    """I_S^(n) vs scipy.integrate.quad."""

    @pytest.mark.parametrize("n", N_VALUES)
    @pytest.mark.parametrize("gamma", GAMMA_VALUES)
    @pytest.mark.parametrize("beta", BETA_VALUES)
    def test_vs_quad(self, n, gamma, beta):
        expected, _ = quad(
            lambda eta: (1 - eta ** beta) * eta ** (n * gamma), 0, 1
        )
        assert abs(I_S(n, gamma, beta) - expected) < TOLERANCE


class TestJQuad:
    """J^(m) vs scipy.integrate.quad."""

    @pytest.mark.parametrize("m", M_VALUES)
    @pytest.mark.parametrize("sigma", SIGMA_VALUES)
    def test_vs_quad(self, m, sigma):
        expected, _ = quad(
            lambda zeta: zeta ** m * (2 - zeta ** sigma), 0, 1
        )
        assert abs(J(m, sigma) - expected) < TOLERANCE


class TestIPhiBoundary:
    """Предельные случаи I_Φ^(n)."""

    def test_n_zero(self):
        """I_Φ^(0) = 1 для любого gamma."""
        for gamma in GAMMA_VALUES:
            assert I_Phi(0, gamma) == pytest.approx(1.0)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_gamma_small(self, n):
        """При gamma → 0: I_Φ^(n) → 1."""
        assert I_Phi(n, 1e-12) == pytest.approx(1.0, abs=1e-10)

    def test_known_value(self):
        """I_Φ^(1) при gamma=1 = 1/2."""
        assert I_Phi(1, 1.0) == pytest.approx(0.5)


class TestISBoundary:
    """Предельные случаи I_S^(n)."""

    @pytest.mark.parametrize("beta", BETA_VALUES)
    def test_n_zero(self, beta):
        """I_S^(0) = beta / (beta + 1)."""
        for gamma in GAMMA_VALUES:
            expected = beta / (beta + 1)
            assert I_S(0, gamma, beta) == pytest.approx(expected)

    @pytest.mark.parametrize("n", N_VALUES)
    @pytest.mark.parametrize("gamma", GAMMA_VALUES)
    def test_beta_zero(self, n, gamma):
        """При beta=0: Sg=0 всюду, I_S^(n) = 0."""
        assert I_S(n, gamma, 0.0) == pytest.approx(0.0, abs=1e-15)

    def test_non_negative(self):
        """I_S^(n) >= 0 (физический смысл: Sg >= 0)."""
        for n in N_VALUES:
            for gamma in GAMMA_VALUES:
                for beta in BETA_VALUES:
                    assert I_S(n, gamma, beta) >= 0.0


class TestJBoundary:
    """Предельные случаи J^(m)."""

    @pytest.mark.parametrize("sigma", SIGMA_VALUES)
    def test_m_zero(self, sigma):
        """J^(0) = 2 − 1/(σ+1)."""
        expected = 2.0 - 1.0 / (sigma + 1.0)
        assert J(0, sigma) == pytest.approx(expected)

    @pytest.mark.parametrize("m", M_VALUES)
    def test_sigma_zero(self, m):
        """При σ=0: Ψ=ζ^0(2−ζ^0)=1, J^(m) = 1/(m+1)."""
        expected = 1.0 / (m + 1.0)
        assert J(m, 0.0) == pytest.approx(expected)

    def test_known_value_sigma1(self):
        """J^(1) при σ=1: 2/2 − 1/3 = 2/3."""
        assert J(1, 1.0) == pytest.approx(2.0 / 3.0)


class TestIntegrationWithProfiles:
    """Интегралы согласованы с параметрами профилей."""

    def test_J_matches_temperature_profile(self):
        """J(m, sigma) совпадает с TemperatureProfile.J(m) (независимые реализации)."""
        from src.profiles.temperature import TemperatureProfile
        tp = TemperatureProfile(r_w=0.1, R_ext=500.0, T_0=350.0, sigma=1.5)
        for m in M_VALUES:
            assert J(m, tp.sigma) == pytest.approx(tp.J(m))

    def test_I_S_decomposition(self):
        """I_S^(n) = I_Φ^(n) − 1/(nγ+β+1) — тождество."""
        for n in N_VALUES:
            for gamma in GAMMA_VALUES:
                for beta in BETA_VALUES:
                    lhs = I_S(n, gamma, beta)
                    rhs = I_Phi(n, gamma) - 1.0 / (n * gamma + beta + 1.0)
                    assert lhs == pytest.approx(rhs)
