"""Тесты HydroPVTtoBlackOilAdapter — пересчёт единиц HydroPVT → BlackOilPVT.

Адаптер — зеркало PrototypePVTAdapter. Проверяем, что делегирование
к StandingFullPVT с пересчётом единиц даёт те же значения, что прямой
вызов Standing.
"""

import numpy as np
import pytest

from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.hydro_to_blackoil_adapter import (
    HydroPVTtoBlackOilAdapter,
)
from gpn_multiphase_solver.units import BAR_TO_PA, CP_TO_PA_S


# ── Fixtures ──

@pytest.fixture
def standing():
    """StandingFullPVT с типичными параметрами."""
    return StandingFullPVT(
        rho_o_std=850.0, rho_g_std=0.85, T0=350.0, Rs0=50.0,
        co_undersaturated=0.0, c_p_oil=2000.0, c_p_gas=1000.0)


P_MAX_PA = 200 * BAR_TO_PA  # 200 бар


@pytest.fixture
def adapter(standing):
    """Адаптер Standing → BlackOilPVT, p_max = 200 бар."""
    return HydroPVTtoBlackOilAdapter(standing, p_max_pa=P_MAX_PA)


# ── Тестовые данные ──

P_BAR = np.array([50.0, 100.0, 150.0, 200.0])
RS = np.array([10.0, 30.0, 50.0, 80.0])


# ═══════════════════════════════════════════════════════════
# A. Методы: пересчёт единиц
# ═══════════════════════════════════════════════════════════

class TestUnitConversion:
    """Каждый метод адаптера = Standing с пересчётом единиц."""

    def test_rs_sat_matches_standing(self, adapter, standing):
        """rs_sat(p_bar) == Rs_eq(p_bar * BAR_TO_PA)."""
        result = adapter.rs_sat(P_BAR)
        expected = standing.Rs_eq(P_BAR * BAR_TO_PA)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    def test_bo_matches_standing(self, adapter, standing):
        """bo(p_bar, rs) == Bo(p_bar * BAR_TO_PA, rs). Bo безразмерный."""
        result = adapter.bo(P_BAR, RS)
        expected = standing.Bo(P_BAR * BAR_TO_PA, RS)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    def test_mu_o_matches_standing(self, adapter, standing):
        """mu_o возвращает сП. mu_o * CP_TO_PA_S == Standing.mu_o (Па·с)."""
        result_cP = adapter.mu_o(P_BAR, RS)
        expected_Pa_s = standing.mu_o(P_BAR * BAR_TO_PA, RS)
        np.testing.assert_allclose(result_cP * CP_TO_PA_S, expected_Pa_s, rtol=1e-12)

    def test_bg_matches_standing(self, adapter, standing):
        """bg(p_bar) == Bg(p_bar * BAR_TO_PA). Bg безразмерный."""
        result = adapter.bg(P_BAR)
        expected = standing.Bg(P_BAR * BAR_TO_PA)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    def test_mu_g_matches_standing(self, adapter, standing):
        """mu_g возвращает сП. mu_g * CP_TO_PA_S == Standing.mu_g (Па·с)."""
        result_cP = adapter.mu_g(P_BAR)
        expected_Pa_s = standing.mu_g(P_BAR * BAR_TO_PA)
        np.testing.assert_allclose(result_cP * CP_TO_PA_S, expected_Pa_s, rtol=1e-12)

    def test_pb_of_rs_matches_standing(self, adapter, standing):
        """pb_of_rs(rs) * BAR_TO_PA == Standing.pb(rs) (Па)."""
        result_bar = adapter.pb_of_rs(RS)
        expected_Pa = standing.pb(RS)
        np.testing.assert_allclose(result_bar * BAR_TO_PA, expected_Pa, rtol=1e-12)


# ═══════════════════════════════════════════════════════════
# B. Атрибуты
# ═══════════════════════════════════════════════════════════

class TestAttributes:
    """Атрибуты rs_values, pb, max_rs, bo_sat, mu_sat."""

    def test_max_rs(self, adapter, standing):
        """max_rs == Rs_eq(p_max)."""
        expected = float(standing.Rs_eq(np.array([P_MAX_PA]))[0])
        assert adapter.max_rs == pytest.approx(expected, rel=1e-12)

    def test_rs_values_monotonic(self, adapter):
        """rs_values строго возрастает (linspace от 0 до max_rs)."""
        assert np.all(np.diff(adapter.rs_values) > 0)

    def test_pb_monotonic(self, adapter):
        """pb строго возрастает для Standing (монотонная Rs→pb)."""
        # pb[0] может быть < 0 при Rs=0 (Standing: pb(0) < 0), но
        # массив всё равно монотонный — diff > 0.
        assert np.all(np.diff(adapter.pb) > 0)

    def test_attributes_shapes(self, adapter):
        """rs_values, pb, bo_sat, mu_sat — массивы длины n_knots=20."""
        assert adapter.rs_values.shape == (20,)
        assert adapter.pb.shape == (20,)
        assert adapter.bo_sat.shape == (20,)
        assert adapter.mu_sat.shape == (20,)


# ═══════════════════════════════════════════════════════════
# C. Скалярные аргументы (RadialBlackOilModel передаёт скаляры)
# ═══════════════════════════════════════════════════════════

class TestScalarArgs:
    """RadialBlackOilModel вызывает PVT со скалярами (float)."""

    def test_bo_scalar(self, adapter, standing):
        """bo(float, float) работает и совпадает со Standing."""
        result = adapter.bo(150.0, 50.0)
        expected = standing.Bo(np.array([150.0 * BAR_TO_PA]), np.array([50.0]))[0]
        assert float(result) == pytest.approx(float(expected), rel=1e-12)

    def test_mu_o_scalar(self, adapter, standing):
        """mu_o(float, float) возвращает скаляр в сП."""
        result_cP = adapter.mu_o(150.0, 50.0)
        expected_Pa_s = standing.mu_o(
            np.array([150.0 * BAR_TO_PA]), np.array([50.0]))[0]
        assert float(result_cP) * CP_TO_PA_S == pytest.approx(
            float(expected_Pa_s), rel=1e-12)

    def test_rs_sat_scalar(self, adapter, standing):
        """rs_sat(float) работает."""
        result = adapter.rs_sat(100.0)
        expected = standing.Rs_eq(np.array([100.0 * BAR_TO_PA]))[0]
        assert float(result) == pytest.approx(float(expected), rel=1e-12)
