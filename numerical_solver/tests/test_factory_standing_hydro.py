"""Тесты Factory с pvt.model='standing' → PrototypeHydroAdapter (FEAT-014).

После FEAT-014 Factory всегда создаёт PrototypeHydroAdapter,
в том числе для аналитических корреляций (Standing).
Проверяем: адаптер создаётся, pipeline работает, ОФП согласованы.
"""

from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import (
    SimulatorFactory, _get_or_create_proto_rp,
)
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.units import BAR_TO_PA


BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"

# baseline.json параметры: p0=20e6, p_wf=15e6, Rs0=50
# pb(Rs0=50) ≈ 9.43 МПа < p_wf → нет разгазирования → однофазный
P0 = 20e6
P_WF = 15e6
R_WELL = 0.1
R_EXT = 50.0


# ═══════════════════════════════════════════════════════════
# A. Factory создаёт PrototypeHydroAdapter для Standing
# ═══════════════════════════════════════════════════════════

class TestFactoryStandingHydro:
    """Factory с pvt.model='standing' → PrototypeHydroAdapter."""

    def test_standing_creates_prototype_hydro(self):
        """HydroSolver = PrototypeHydroAdapter при pvt.model='standing'."""
        config = load_config(BASELINE)
        simulator, _ = SimulatorFactory.from_config(config)
        assert isinstance(simulator._hydro, PrototypeHydroAdapter)

    def test_standing_pipeline_runs(self):
        """baseline.json → Factory → run → history содержит данные."""
        config = load_config(BASELINE)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        assert history.n_saved > 1
        # Финальное давление < начального (добыча идёт)
        assert history.states[-1].p[0] < P0

    def test_standing_well_rate_positive(self):
        """Дебит нефти > 0 при добыче."""
        config = load_config(BASELINE)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)
        assert history.well_data[-1].q_o_std > 0

    def test_standing_dupuit_pressure(self):
        """Профиль давления ≈ лог-профиль Дюпюи (однофазный, Newton).

        baseline.json: 2 интервала, последний p_wf=10e6. Newton даёт
        нестационарное решение, rtol=1e-2.
        """
        config = load_config(BASELINE)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        r = simulator._grid.r_centers
        p_wf_last = config.time.history[-1].p_wf  # 10e6 Па
        p_exact = p_wf_last + (P0 - p_wf_last) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
        np.testing.assert_allclose(
            history.states[-1].p, p_exact, rtol=1e-2)


# ═══════════════════════════════════════════════════════════
# B. CoreyRP → TabulatedRelPerm
# ═══════════════════════════════════════════════════════════

class TestCoreyToTabulated:
    """CoreyRP → TabulatedRelPerm через _get_or_create_proto_rp."""

    def test_kro_matches(self):
        """Табулированная kro ≈ CoreyRP.kro на тестовых точках."""
        corey = CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0)
        proto_rp = _get_or_create_proto_rp(corey)

        Sg_test = np.array([0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
        # np.interp на 101 точке — ошибка интерполяции < 1e-4
        np.testing.assert_allclose(
            proto_rp.kro(Sg_test), corey.kro(Sg_test), atol=1e-4)

    def test_krg_matches(self):
        """Табулированная krg ≈ CoreyRP.krg на тестовых точках."""
        corey = CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0)
        proto_rp = _get_or_create_proto_rp(corey)

        Sg_test = np.array([0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
        np.testing.assert_allclose(
            proto_rp.krg(Sg_test), corey.krg(Sg_test), atol=1e-4)
