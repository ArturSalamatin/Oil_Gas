"""VAL-001: Однофазный стационарный приток (формула Дюпюи).

Аналитический валидационный кейс.
Условия: Sg=0, co=0, μ_JT=0, L=0, стационар.
mob_o = kro/(μ_o·Bo) = 1/(μ_o·Bo) = const → формулы точные.

Эталон:
  q_o_std = 2πkh · mob_o · (p_ext − p_wf) / ln(R_ext/r_w)
  p(r) = p_wf + (p_ext − p_wf) · ln(r/r_w) / ln(R_ext/r_w)

Метрики:
  дебит rel=1e-10, давление rel=1e-12, G_o=const rel=1e-12,
  u·r=const rel=1e-10, GOR=Rs0 rel=1e-12, T→T_ext atol=1 К.
"""

from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.io.config import load_config, RockConfig
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.output import save_npz
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.hydro.analytical import AnalyticalHydroSolver
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.simulator import Simulator, TimeSchedule, ScheduleInterval


# ── Пути и константы ────────────────────────────────────────

VAL001_PATH = Path(__file__).parent.parent / "configs" / "val001.json"

# Параметры из val001.json (дублируются для эталонных формул)
R_WELL = 0.1        # м
R_EXT = 50.0        # м
H = 10.0            # м
K = 1e-13            # м²
P_EXT = 20e6         # Па
P_WF = 15e6          # Па
T0 = 350.0           # К
RS0 = 50.0           # м³ст/м³ст

# Эталонные PVT-значения (Standing, co=0, Rs=50, T=350 К)
# Bo(Rs=50) = 1.1672..., μ_o(Rs=50) = 9.4790e-4 Па·с
MOB_O = 903.8407518315244   # 1/(μ_o · Bo), 1/(Па·с)
Q_EXACT = 2.0 * np.pi * K * H * MOB_O * (P_EXT - P_WF) / np.log(R_EXT / R_WELL)


# ── Helpers ─────────────────────────────────────────────────

def _run_val001():
    """Загрузить val001.json, запустить, вернуть (simulator, history)."""
    config = load_config(VAL001_PATH)
    simulator, initial = SimulatorFactory.from_config(config)
    history = simulator.run(initial)
    return simulator, history


# ═══════════════════════════════════════════════════════════
# A. Дебит и давление (шаг 2)
# ═══════════════════════════════════════════════════════════

class TestDupuitRate:
    """Дебит q_o_std должен совпадать с формулой Дюпюи."""

    def test_rate_matches_dupuit(self):
        """q_o_std = 2πkh·mob_o·Δp/ln(R/rw). mob_o = const → точная формула."""
        _, history = _run_val001()
        q_o = history.well_data[-1].q_o_std
        # q_o_std > 0 (добыча), rel=1e-10 (mob_o=const → точно)
        assert q_o == pytest.approx(Q_EXACT, rel=1e-10)

    def test_rate_positive(self):
        """Дебит при добыче > 0."""
        _, history = _run_val001()
        assert history.well_data[-1].q_o_std > 0


class TestDupuitPressure:
    """Профиль p(r) = лог-формула на центрах ячеек."""

    def test_pressure_log_profile(self):
        """p(r_j) = p_wf + Δp·ln(r_j/rw)/ln(R/rw) на центрах масс ячеек."""
        sim, history = _run_val001()
        r = sim._grid.r_centers
        p_exact = P_WF + (P_EXT - P_WF) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
        # AnalyticalHydroSolver строит этот профиль точно → rel=1e-12
        np.testing.assert_allclose(history.states[-1].p, p_exact, rtol=1e-12)


class TestStationaryFlux:
    """G_o = const на всех гранях, u·r = const (стационар, mob_o=const)."""

    def test_G_o_constant(self):
        """G_o одинаков на всех N+1 гранях (забой, внутренние, контур).

        При const mob_o проводимости T и перепады dp сокращаются:
        G_o = -2πkh·mob_o·Δp/ln(R/rw) = const.
        Знак: G_o < 0 (поток к скважине). См. конвенции-знаков.md.
        """
        _, history = _run_val001()
        G_o = history.hydro_results[-1].G_o
        # G_o < 0 при добыче
        assert G_o[0] < 0
        np.testing.assert_allclose(G_o, G_o[0], rtol=1e-12)

    def test_u_r_constant(self):
        """u_o·r = const — закон сохранения в цилиндрических координатах."""
        sim, history = _run_val001()
        u_o = history.hydro_results[-1].u_o
        r_f = sim._grid.r_faces
        u_r = u_o * r_f
        # u_r < 0 (поток к скважине)
        assert u_r[0] < 0
        np.testing.assert_allclose(u_r, u_r[0], rtol=1e-10)


# ═══════════════════════════════════════════════════════════
# B. Баланс масс и GOR (шаг 3)
# ═══════════════════════════════════════════════════════════

class TestMassBalance:
    """Баланс масс нефтяного компонента: G_o[j+1] − G_o[j] = 0 (стационар)."""

    def test_oil_mass_balance(self):
        """Невязка G_o на каждой ячейке ≈ 0 (стационар)."""
        _, history = _run_val001()
        G_o = history.hydro_results[-1].G_o
        # Невязка = G_o[j+1] - G_o[j] для j=0..N-1
        residual = np.diff(G_o)
        # Нормируем на |G_o[0]|
        np.testing.assert_allclose(
            residual / np.abs(G_o[0]), 0.0, atol=1e-12)


class TestGOR:
    """GOR = Rs0 (весь газ растворён, Sg=0)."""

    def test_gor_equals_rs0(self):
        """−G_g[0] / (−G_o[0]) = Rs0. При Sg=0 свободного газа нет."""
        _, history = _run_val001()
        G_o = history.hydro_results[-1].G_o
        G_g = history.hydro_results[-1].G_g
        gor = (-G_g[0]) / (-G_o[0])
        assert gor == pytest.approx(RS0, rel=1e-12)


# ═══════════════════════════════════════════════════════════
# C. Температура (шаг 4)
# ═══════════════════════════════════════════════════════════

class TestTemperature:
    """T → T_ext при μ_JT=0, L=0 (без тепловых источников)."""

    def test_temperature_converges(self):
        """Начальная T=340 К → T_ext=350 К при R=5 м, N=5, 500 часов.

        Маленькая сетка R=5 м: при R=50 м конвекция не успевает
        за 500 часов (max|T−350| ≈ 10 К). При R=5 м конвергенция
        до машинной точности.
        """
        grid = LogRadialGrid(r_well=0.1, R_ext=5.0, h=10.0, N=5, k=1e-13)
        pvt = StandingFullPVT(
            rho_o_std=850.0, rho_g_std=0.85, T0=350.0, Rs0=50.0,
            co_undersaturated=0.0, mu_JT_oil_val=0.0,
            mu_JT_gas_val=0.0, L_degas_val=0.0)
        rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
        hydro = AnalyticalHydroSolver(grid, pvt, rp)
        rock = RockConfig(porosity=0.2, permeability=1e-13)
        energy = TridiagEnergySolver(grid, pvt, rock)

        bc = BoundaryConditions(
            well=PressureControl(15e6), p_ext=20e6,
            T_ext=350.0, Rs_ext=50.0, Sg_ext=0.0)
        schedule = TimeSchedule(
            dt_integration=3600.0,
            intervals=[ScheduleInterval(dt=1800000.0, bc=bc)])
        sim = Simulator(
            grid=grid, hydro=hydro, energy=energy,
            pvt=pvt, schedule=schedule)

        # T_init = 340 К ≠ T_ext = 350 К
        initial = SimulationState(
            p=np.full(5, 20e6), Sg=np.zeros(5),
            Rs=np.full(5, 50.0), T=np.full(5, 340.0),
            regime=np.full(5, 2, dtype=int), t=0.0)

        history = sim.run(initial)
        T_final = history.states[-1].T
        assert np.max(np.abs(T_final - 350.0)) < 1.0


# ═══════════════════════════════════════════════════════════
# D. Pipeline: JSON → run → save_npz → load (шаг 5)
# ═══════════════════════════════════════════════════════════

class TestPipeline:
    """Сквозной pipeline: val001.json → Factory → run → npz → load."""

    def test_pipeline_roundtrip(self, tmp_path):
        """JSON → Factory → run → save_npz → np.load → проверка."""
        config = load_config(VAL001_PATH)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        npz_path = tmp_path / "val001.npz"
        save_npz(history, simulator._grid, npz_path)

        data = np.load(npz_path)

        # 1 интервал 86400 с, dt=3600 → 24 подшага + 1 начальный = 25
        assert data['times'][-1] == pytest.approx(86400.0)
        assert data['q_o_std'][-1] > 0
        assert data['p'].shape == (25, 20)
        assert data['T'].shape == (25, 20)
        assert data['r'].shape == (20,)
