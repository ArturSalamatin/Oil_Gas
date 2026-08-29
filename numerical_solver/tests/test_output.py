"""Тесты для io/output.py (фаза 7).

Проверяет:
  A. save_npz → np.load: roundtrip, все массивы поэлементно
  B. save_csv: формат, заголовок, значения
  C. history_to_arrays: размеры, значения
  D. Визуализация: функции не падают, возвращают Axes
  E. Минимальная история: 1 шаг (начальное состояние)
"""

from pathlib import Path
import numpy as np
import pytest
import matplotlib
matplotlib.use('Agg')  # headless backend для CI

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import (
    SimulationState, HydroResult, WellData, SimulationHistory,
)
from gpn_multiphase_solver.io.config import load_config, RockConfig, OutputConfig
from gpn_multiphase_solver.io.output import (
    history_to_arrays, save_npz, save_csv,
    plot_profiles, plot_wellbore_dynamics, plot_well_rate, plot_2d_map,
)
from gpn_multiphase_solver.hydro.analytical import AnalyticalHydroSolver
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.simulator import Simulator, TimeSchedule, ScheduleInterval
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.state import BoundaryConditions
from gpn_multiphase_solver.factory import SimulatorFactory

BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"

# ── Параметры ────────────────────────────────────────────────

N = 5
R_WELL = 0.1
R_EXT = 10.0
H = 10.0
K_PERM = 1e-13
P0 = 20e6
P_WF = 10e6
T0 = 350.0
RS0 = 50.0


# ── Fixture: маленькая симуляция ─────────────────────────────

@pytest.fixture
def small_history():
    """Симуляция: 3 шага, N=5 ячеек."""
    grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
    pvt = StandingFullPVT(850.0, 0.85, T0, RS0, 0.0, 2000.0, 1000.0)
    rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
    hydro = AnalyticalHydroSolver(grid, pvt, rp)
    rock = RockConfig(porosity=0.2, permeability=K_PERM)
    energy = TridiagEnergySolver(grid, pvt, rock)

    bc = BoundaryConditions(
        well=PressureControl(P_WF), p_ext=P0,
        T_ext=T0, Rs_ext=RS0)
    schedule = TimeSchedule(3600.0, [ScheduleInterval(dt=10800.0, bc=bc)])
    sim = Simulator(grid, hydro, energy, pvt, schedule)

    initial = SimulationState(
        p=np.full(N, P0), Sg=np.zeros(N), Rs=np.full(N, RS0),
        T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
    return sim.run(initial), grid


# ═══════════════════════════════════════════════════════════
# A. history_to_arrays
# ═══════════════════════════════════════════════════════════

class TestHistoryToArrays:
    def test_keys(self, small_history):
        history, _ = small_history
        arrays = history_to_arrays(history)
        expected_keys = {'times', 'p', 'T', 'Sg', 'Rs',
                         'q_o_std', 'q_g_std', 'p_wf', 'T_wf'}
        assert set(arrays.keys()) == expected_keys

    def test_times_shape(self, small_history):
        history, _ = small_history
        arrays = history_to_arrays(history)
        # 1 начальный + 3 подшага = 4
        assert arrays['times'].shape == (history.n_saved,)

    def test_p_shape(self, small_history):
        history, _ = small_history
        arrays = history_to_arrays(history)
        assert arrays['p'].shape == (history.n_saved, N)

    def test_times_values(self, small_history):
        history, _ = small_history
        arrays = history_to_arrays(history)
        assert arrays['times'][0] == 0.0
        assert arrays['times'][-1] == pytest.approx(10800.0)

    def test_q_o_std_shape(self, small_history):
        history, _ = small_history
        arrays = history_to_arrays(history)
        assert arrays['q_o_std'].shape == (history.n_saved,)

    def test_q_o_std_last_positive(self, small_history):
        """Дебит на последнем шаге > 0 (добыча)."""
        history, _ = small_history
        arrays = history_to_arrays(history)
        assert arrays['q_o_std'][-1] > 0


# ═══════════════════════════════════════════════════════════
# B. save_npz → roundtrip
# ═══════════════════════════════════════════════════════════

class TestSaveNpz:
    def test_roundtrip(self, small_history, tmp_path):
        """Записать → прочитать → проверить поэлементно."""
        history, grid = small_history
        path = tmp_path / "test.npz"
        save_npz(history, grid, path)

        data = np.load(path)
        arrays = history_to_arrays(history)

        # r
        np.testing.assert_allclose(data['r'], grid.r_centers, rtol=1e-14)
        # Все массивы из history
        for key in ['times', 'p', 'T', 'Sg', 'Rs',
                    'q_o_std', 'q_g_std', 'p_wf', 'T_wf']:
            np.testing.assert_allclose(
                data[key], arrays[key], rtol=1e-14,
                err_msg=f"Mismatch in {key}")

    def test_file_exists(self, small_history, tmp_path):
        history, grid = small_history
        path = tmp_path / "out.npz"
        save_npz(history, grid, path)
        assert path.exists()


# ═══════════════════════════════════════════════════════════
# C. save_csv
# ═══════════════════════════════════════════════════════════

class TestSaveCsv:
    def test_header(self, small_history, tmp_path):
        """Первая строка — заголовок с правильными столбцами."""
        history, grid = small_history
        path = tmp_path / "test.csv"
        save_csv(history, grid, path)

        with open(path, encoding='utf-8') as f:
            header = f.readline().strip()
        assert header == "step,time_s,r_m,p_Pa,T_K,Sg,Rs"

    def test_row_count(self, small_history, tmp_path):
        """Число строк данных = n_saved * N."""
        history, grid = small_history
        path = tmp_path / "test.csv"
        save_csv(history, grid, path)

        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
        # 1 заголовок + n_saved * N строк данных
        assert len(lines) == 1 + history.n_saved * N

    def test_first_data_row(self, small_history, tmp_path):
        """Первая строка данных: step=0, time=0, r=r[0], p=p0."""
        history, grid = small_history
        path = tmp_path / "test.csv"
        save_csv(history, grid, path)

        with open(path, encoding='utf-8') as f:
            f.readline()  # заголовок
            row = f.readline().strip().split(',')

        assert int(row[0]) == 0           # step
        assert float(row[1]) == 0.0       # time
        assert float(row[2]) == pytest.approx(grid.r_centers[0], rel=1e-5)
        assert float(row[3]) == pytest.approx(P0, rel=1e-5)  # p


# ═══════════════════════════════════════════════════════════
# D. Визуализация — не падает, возвращает Axes
# ═══════════════════════════════════════════════════════════

class TestPlots:
    def test_plot_profiles(self, small_history):
        history, grid = small_history
        ax = plot_profiles(history, grid, [0.0, 10800.0], field='T')
        assert ax is not None

    def test_plot_profiles_pressure(self, small_history):
        history, grid = small_history
        ax = plot_profiles(history, grid, [10800.0], field='p')
        assert ax is not None

    def test_plot_wellbore_dynamics(self, small_history):
        history, _ = small_history
        axes = plot_wellbore_dynamics(history)
        assert len(axes) == 3

    def test_plot_well_rate(self, small_history):
        history, _ = small_history
        ax = plot_well_rate(history)
        assert ax is not None

    def test_plot_2d_map(self, small_history):
        history, grid = small_history
        ax = plot_2d_map(history, grid, field='T')
        assert ax is not None

    def test_plot_2d_map_pressure(self, small_history):
        history, grid = small_history
        ax = plot_2d_map(history, grid, field='p')
        assert ax is not None


# ═══════════════════════════════════════════════════════════
# E. Минимальная история (1 шаг)
# ═══════════════════════════════════════════════════════════

class TestMinimalHistory:
    def test_single_step_npz(self, tmp_path):
        """SimulationHistory с одним шагом — save_npz не падает."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, 3, K_PERM)
        history = SimulationHistory()
        state = SimulationState(
            p=np.full(3, P0), Sg=np.zeros(3), Rs=np.full(3, RS0),
            T=np.full(3, T0), regime=np.full(3, 2, dtype=int), t=0.0)
        Z = np.zeros(4)
        hydro = HydroResult(
            state=state, G_o=Z, G_g=Z, G_free_gas=Z,
            Q_o=Z, Q_g=Z, u_o=Z, u_g=Z,
            m_o=Z, m_g=Z, Gm_o=Z, Gm_g=Z)
        well = WellData(0.0, 0.0, 0.0, 0.0, P0, T0)
        history.append(t=0.0, state=state, hydro=hydro, well=well)

        path = tmp_path / "single.npz"
        save_npz(history, grid, path)
        data = np.load(path)
        assert data['times'].shape == (1,)
        assert data['p'].shape == (1, 3)


# ═══════════════════════════════════════════════════════════
# F. Factory → run → save (сквозной тест)
# ═══════════════════════════════════════════════════════════

class TestEndToEnd:
    def test_baseline_to_npz(self, tmp_path):
        """baseline.json → Simulator.run() → save_npz → load → проверка."""
        config = load_config(BASELINE)
        simulator, initial_state = SimulatorFactory.from_config(config)
        history = simulator.run(initial_state)

        path = tmp_path / "baseline.npz"
        save_npz(history, simulator._grid, path)

        data = np.load(path)
        assert data['times'][-1] == pytest.approx(345600.0)
        assert data['p'].shape[1] == config.grid.N
        assert data['q_o_std'][-1] > 0
