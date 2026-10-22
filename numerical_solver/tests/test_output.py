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
    history_to_arrays, save_npz, save_csv, save_well_csv,
    plot_profiles, plot_wellbore_dynamics, plot_well_rate, plot_2d_map,
    plot_pvt_properties, _round_rs_rows, _pvto_rows,
)
from ._doubles import LogProfileHydroStub
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
    hydro = LogProfileHydroStub(grid, pvt, rp)
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
# C2. save_well_csv — скважинная история (одна строка на шаг)
# ═══════════════════════════════════════════════════════════

WELL_HEADER = ("time_s,time_day,q_o_m3st_s,q_g_m3st_s,"
               "m_o_kg_s,m_g_kg_s,p_wf_Pa,T_wf_K,GOR_m3st_m3st")


class TestSaveWellCsv:
    def test_header(self, small_history, tmp_path):
        """Заголовок содержит все 6 полей WellData + time_day + GOR."""
        history, _ = small_history
        path = tmp_path / "well.csv"
        save_well_csv(history, path)

        with open(path, encoding='utf-8') as f:
            header = f.readline().strip()
        assert header == WELL_HEADER

    def test_row_count(self, small_history, tmp_path):
        """Одна строка на сохранённый шаг (в отличие от save_csv — без ячеек)."""
        history, _ = small_history
        path = tmp_path / "well.csv"
        save_well_csv(history, path)

        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 1 + history.n_saved

    def test_values_match_well_data(self, small_history, tmp_path):
        """Значения последней строки совпадают с WellData последнего шага."""
        history, _ = small_history
        path = tmp_path / "well.csv"
        save_well_csv(history, path)

        with open(path, encoding='utf-8') as f:
            rows = f.readlines()
        row = rows[-1].strip().split(',')
        w = history.well_data[-1]

        assert float(row[0]) == pytest.approx(history.times[-1], rel=1e-9)
        assert float(row[1]) == pytest.approx(history.times[-1] / 86400.0, rel=1e-9)
        assert float(row[2]) == pytest.approx(w.q_o_std, rel=1e-5)
        assert float(row[3]) == pytest.approx(w.q_g_std, rel=1e-5)
        assert float(row[4]) == pytest.approx(w.m_o_well, rel=1e-5)
        assert float(row[5]) == pytest.approx(w.m_g_well, rel=1e-5)
        assert float(row[6]) == pytest.approx(w.p_wf, rel=1e-5)
        assert float(row[7]) == pytest.approx(w.T_wf, rel=1e-5)

    def test_gor_value(self, small_history, tmp_path):
        """GOR = q_g_std / q_o_std при добыче (q_o > 0)."""
        history, _ = small_history
        path = tmp_path / "well.csv"
        save_well_csv(history, path)

        with open(path, encoding='utf-8') as f:
            rows = f.readlines()
        row = rows[-1].strip().split(',')
        w = history.well_data[-1]

        assert w.q_o_std > 0.0, "фикстура должна давать добычу на последнем шаге"
        assert float(row[8]) == pytest.approx(w.q_g_std / w.q_o_std, rel=1e-5)

    def test_gor_empty_when_no_oil_rate(self, tmp_path):
        """При q_o_std <= 0 поле GOR пустое (деления на ноль не происходит)."""
        # Первый (начальный) шаг: скважина ещё не работает, q_o_std = 0.
        history = SimulationHistory()
        state = SimulationState(
            p=np.full(N, P0), Sg=np.zeros(N), Rs=np.full(N, RS0),
            T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
        zeros = np.zeros(N + 1)
        hydro = HydroResult(
            state=state,
            G_o=zeros, G_g=zeros, G_free_gas=zeros,
            Q_o=zeros, Q_g=zeros, u_o=zeros, u_g=zeros,
            m_o=zeros, m_g=zeros, Gm_o=zeros, Gm_g=zeros,
            p_wf=P0)
        well = WellData(q_o_std=0.0, q_g_std=0.0, m_o_well=0.0,
                        m_g_well=0.0, p_wf=P0, T_wf=T0)
        history.append(0.0, state, hydro, well)

        path = tmp_path / "well.csv"
        save_well_csv(history, path)

        with open(path, encoding='utf-8') as f:
            f.readline()
            row = f.readline().rstrip('\n').split(',')
        assert row[8] == "", "GOR при нулевом дебите нефти должен быть пустым"


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

    def test_profile_legend_in_days(self, small_history):
        """Момент в легенде профиля — в сутках (правило проекта, FEAT-022).

        small_history: один интервал 10800 с, записи t = 0 и 10800 с.
        Ожидание: подписи «t = 0 сут» и «t = 0.125 сут» (10800/86400).
        Аргумент times_to_plot по-прежнему в секундах — API не меняется.
        Ловит: возврат подписи в секунды или перевод, сделанный дважды.
        """
        history, grid = small_history
        ax = plot_profiles(history, grid, [0.0, 10800.0], field='T')
        labels = [t.get_text() for t in ax.get_legend().get_texts()]
        assert labels == ["t = 0 сут", "t = 0.125 сут"]

    def test_time_axes_in_days(self, small_history):
        """Оси времени — в сутках: и подпись, и сами данные (FEAT-022).

        Последняя запись small_history — 10800 с = 0.125 сут. Проверяется
        не только подпись оси, но и абсцисса кривой: переименованная ось
        при данных в секундах — худший вариант ошибки.
        """
        history, grid = small_history
        ax = plot_well_rate(history)
        assert ax.get_xlabel() == "t, сут"
        assert ax.get_lines()[0].get_xdata()[-1] == pytest.approx(0.125)

        axes = plot_wellbore_dynamics(history)
        assert axes[2].get_xlabel() == "t, сут"
        assert axes[0].get_lines()[0].get_xdata()[-1] == pytest.approx(0.125)

        ax = plot_2d_map(history, grid, field='T')
        assert ax.get_ylabel() == "t, сут"


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
            m_o=Z, m_g=Z, Gm_o=Z, Gm_g=Z,
            p_wf=P0)
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
        save_npz(history, simulator.grid, path)

        data = np.load(path)
        assert data['times'][-1] == pytest.approx(345600.0)
        assert data['p'].shape[1] == config.grid.N
        assert data['q_o_std'][-1] > 0


# ═══════════════════════════════════════════════════════════
# G. plot_pvt_properties: слой ядра (FEAT-017)
# ═══════════════════════════════════════════════════════════

class TestPvtPropertiesCore:
    """Ядерная функция графика PVT.

    Смысл слоя (FEAT-017, §4.0): examples/ не входит в дистрибутив
    (pyproject.toml: include = ["gpn_multiphase_solver*"]), поэтому функция,
    лежащая только там, недоступна тому, кто поставил пакет через pip.
    Ядерная версия обязана работать от одного объекта PVT — без config,
    без фабрики, без SimulationHistory.
    """

    def test_core_pvt_plot_standalone(self):
        """Функция работает от вручную собранного PVT, без config и прогона.

        Это ровно тот сценарий, ради которого слой ядра и вводится:
        пользователь пакета собрал PVT сам и хочет посмотреть свойства.
        Rs0 = 50 м³ст/м³ст, ось 6.4…22 МПа: на панели mu_o насыщенная
        кривая, 6 тонких ветвей R_s = 40, 60, …, 140 и жирная ветвь R_s,0
        (FEAT-028). Кривые ищутся по gid, а не по числу линий: подсчёт
        «линий с >2 точками» сбивают маркеры узлов и вертикали.
        """
        import matplotlib.pyplot as plt
        pvt = StandingFullPVT(rho_o_std=850.0, rho_g_std=0.9,
                              T0=350.0, Rs0=50.0)
        axes = plot_pvt_properties(pvt, 50.0, (8e6, 20e6))

        assert axes.shape == (2, 3)
        counts = tuple(len(_pvto_lines(axes[0, 0], gid)) for gid in
                       ("pvto_saturated", "pvto_branch", "pvto_rs0"))
        plt.close(axes[0, 0].figure)
        assert counts == (1, 6, 1), (
            f"на панели mu_o ожидались насыщенная, 6 ветвей и R_s,0, "
            f"нашлось {counts}")

    def test_core_pvt_plot_has_no_config_dependency(self):
        """io/output.py не импортирует factory и io.config.

        Структурная защита границы слоёв: стоит ядру начать тянуть config
        «ради одной подписи» — и функция перестанет решать задачу
        пользователя пакета, ради которой она в ядро и вынесена.
        Подпись модели приходит готовой строкой в параметре label.
        """
        import ast

        src = (Path(__file__).parent.parent / "gpn_multiphase_solver"
               / "io" / "output.py")
        tree = ast.parse(src.read_text(encoding="utf-8"))

        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                # Относительные импорты: '..state' -> level=2, module='state'
                imported.append("." * node.level + (node.module or ""))

        forbidden = [m for m in imported
                     if "factory" in m or "config" in m]
        assert not forbidden, (
            f"io/output.py тянет сборку моделей: {forbidden}. "
            f"Ядро обязано принимать готовый объект PVT, а не собирать его")


# ═══════════════════════════════════════════════════════════
# H. plot_pvt_properties в стиле таблицы PVTO (FEAT-028)
# ═══════════════════════════════════════════════════════════

def _pvto_lines(ax, gid):
    """Кривые панели с разметкой gid (ядро размечает кривые PVTO через set_gid)."""
    return [ln for ln in ax.get_lines() if ln.get_gid() == gid]


def _standing_pvt(Rs0):
    """PVT тестов ядра: rho_o_ст = 850, rho_g_ст = 0.9 кг/м³, T0 = 350 К."""
    return StandingFullPVT(rho_o_std=850.0, rho_g_std=0.9, T0=350.0, Rs0=Rs0)


class TestPvtoCore:
    """Рисунок PVT как таблица PVTO на корреляции Стендинга — без конфига и расчёта.

    На оси 6.4…22 МПа (p_range 8…20 МПа) R_s^eq = 33.55…145.14 м³ст/м³ст,
    p_b(50) = 8.98 МПа (проба vault/issues/feat-028/probes/pvto_numbers.py).
    """

    def test_round_rs_rows_standing(self):
        """Строки корреляции — кратные наименьшему шагу, дающему не больше 7 строк.

        На оси 6.4…22 МПа R_s^eq = 33.55…145.14 м³ст/м³ст: шаг 10 дал бы
        11 строк (40…140), шаг 20 — 6. Числа круглые, как строки настоящей
        таблицы PVTO (решение 2026-10-03), а не 63.9, 81.3…
        """
        rows = _round_rs_rows(_standing_pvt(50.0), np.linspace(6.4e6, 22e6, 800))
        assert rows.tolist() == [40.0, 60.0, 80.0, 100.0, 120.0, 140.0]

    def test_pvto_rows_exclude_rs0(self):
        """Ветвь R_s,0 из веера исключена — она рисуется отдельно, жирной.

        При R_s,0 = 60, совпадающем со строкой, тонкой ветви 60 быть не должно:
        иначе под жирной зелёной лежала бы серая той же формы.
        """
        rows = _pvto_rows(_standing_pvt(60.0), np.linspace(6.4e6, 22e6, 800),
                          60.0, None)
        assert rows.tolist() == [40.0, 80.0, 100.0, 120.0, 140.0]

    def test_branches_start_on_saturated_curve(self):
        """Ветвь начинается на насыщенной кривой: f(p_b(R_s,i), R_s,i) = f(p_b, R_s^eq(p_b)).

        Это и есть смысл таблицы PVTO: строка R_s,i — нефть, насыщенная при
        p_b(R_s,i) и сжимаемая выше. Требует R_s^eq(p_b(R)) = R (у Стендинга
        5.7e-14) и вставки p_b(R_s,i) в сетку по p: первая точка ветви и точка
        насыщенной при том же x вычислены из одного числа p. Проверяется на
        всех четырёх панелях нефти; 6 тонких ветвей + R_s,0 = 7 стыков.
        """
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3)
        plot_pvt_properties(_standing_pvt(50.0), 50.0, (8e6, 20e6), axes=axes)
        for ax in (axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 2]):
            sat = (_pvto_lines(ax, "pvto_saturated")
                   + _pvto_lines(ax, "pvto_saturated_extrap"))
            sx = np.concatenate([ln.get_xdata() for ln in sat])
            sy = np.concatenate([ln.get_ydata() for ln in sat])
            joined = 0
            for ln in _pvto_lines(ax, "pvto_branch") + _pvto_lines(ax, "pvto_rs0"):
                x0, y0 = ln.get_xdata()[0], ln.get_ydata()[0]
                if x0 <= sx.min():
                    continue        # ветвь начата левее оси — стыка на рисунке нет
                idx = np.flatnonzero(sx == x0)
                assert idx.size, f"{ax.get_ylabel()}: нет точки насыщенной при p = {x0} МПа"
                assert y0 == pytest.approx(sy[idx[0]], rel=1e-9), (
                    f"{ax.get_ylabel()}: ветвь при p = {x0} МПа оторвана от насыщенной")
                joined += 1
            assert joined == 7, f"{ax.get_ylabel()}: стыков {joined}, ожидалось 7"
        plt.close(fig)

    def test_rs0_branch_is_thickest(self):
        """Ветвь R_s,0 на каждой панели нефти одна и толще всех тонких ветвей."""
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3)
        plot_pvt_properties(_standing_pvt(50.0), 50.0, (8e6, 20e6), axes=axes)
        for ax in (axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 2]):
            rs0 = _pvto_lines(ax, "pvto_rs0")
            thin = max(ln.get_linewidth() for ln in _pvto_lines(ax, "pvto_branch"))
            assert len(rs0) == 1 and rs0[0].get_linewidth() > thin, ax.get_ylabel()
        plt.close(fig)

    def test_mu_o_panel_log_scale(self):
        """mu_o — в логарифмической шкале, B_o — в линейной (решение 2026-10-03).

        У примера 14 веер mu_o 4.7e-4…1.6e-2 Па·с: на линейной оси рабочая
        ветвь R_s,0 = 150 (0.51…0.53 сП) сжалась бы в нижние 3 % панели.
        """
        axes = plot_pvt_properties(_standing_pvt(50.0), 50.0, (8e6, 20e6))
        assert axes[0, 0].get_yscale() == "log"
        assert axes[0, 2].get_yscale() == "linear"
        import matplotlib.pyplot as plt
        plt.close(axes[0, 0].figure)

    def test_legend_entries_independent_of_branch_count(self):
        """В легенде mu_o три записи: насыщенная, «ветви R_s = const», R_s,0.

        Все тонкие ветви — одной записью: у примера 14 их 17, по записи на
        ветвь легенда закрыла бы панель (решение 2026-10-03). Табличный
        случай (≤ 5 записей при 17 ветвях) — test_table_branches_are_pvto_rows.
        """
        axes = plot_pvt_properties(_standing_pvt(50.0), 50.0, (8e6, 20e6))
        labels = [t.get_text() for t in axes[0, 0].get_legend().get_texts()]
        import matplotlib.pyplot as plt
        plt.close(axes[0, 0].figure)
        assert len(labels) == 3, labels

    def test_standing_has_no_extrapolation_segment(self):
        """У корреляции насыщенная кривая сплошная по всей оси — пунктира нет.

        Пунктир «экстраполяция за строки таблицы» означает выход за строки
        PVTO; у аналитической корреляции строк нет.
        """
        axes = plot_pvt_properties(_standing_pvt(50.0), 50.0, (8e6, 20e6))
        import matplotlib.pyplot as plt
        plt.close(axes[0, 0].figure)
        assert not any(_pvto_lines(ax, "pvto_saturated_extrap")
                       for ax in axes.ravel())

    def test_single_phase_draws_fan(self):
        """При R_s,0 = 0 рисуются насыщенная кривая и веер, как у двухфазных.

        Рисунок описывает модель PVT, а не расчёт (решение 2026-10-03;
        прежний тест требовал обратного). p_b(0) = -0.176 МПа левее оси
        12…22 МПа: ветвь R_s,0 = 0 — горизонталь от левого края, вертикали
        p_b нет. Насыщенная кривая растягивает ось R_s выше 100 м³ст/м³ст.
        """
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3)
        plot_pvt_properties(_standing_pvt(0.0), 0.0, (15e6, 20e6), axes=axes)
        ax_rs = axes[0, 1]
        rs0 = _pvto_lines(ax_rs, "pvto_rs0")
        assert len(rs0) == 1
        assert rs0[0].get_xdata()[0] == pytest.approx(12.0)
        assert np.all(rs0[0].get_ydata() == 0.0)
        assert ax_rs.get_ylim()[1] > 100.0
        assert len(_pvto_lines(ax_rs, "pvto_branch")) >= 3
        # Ни одна линия (в том числе вертикаль p_b) не уходит левее оси.
        assert all(np.min(ln.get_xdata()) >= 12.0 - 1e-12
                   for ax in axes.ravel() for ln in ax.get_lines())
        plt.close(fig)
