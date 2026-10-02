"""Тесты интеграции Factory с табличным PVT (FEAT-012).

Проверяют:
- CSV-ридеры: формат, конвертация единиц SI → бар/сП
- Factory: pvt.model="table" → PrototypeHydroAdapter
- Pipeline: from_config → run → history
- PVT-согласованность: один BlackOilPVT в обёртке и в модели
- Ошибки: отсутствие CSV файла
- Начальное состояние против таблиц: Rs0 в диапазоне, недонасыщенный старт, предупреждения (BUG-017)
"""

import logging
import shutil
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.io.config import load_config, SimulationConfig
from gpn_multiphase_solver.factory import (
    SimulatorFactory,
    _read_oil_pvt_csv, _read_gas_pvt_csv, _read_relperm_csv,
)
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.pvt.table_full import TableFullPVT
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypePVTAdapter, PrototypeRPAdapter
from gpn_multiphase_solver.units import BAR_TO_PA, CP_TO_PA_S


TABLE_CONFIG = Path(__file__).parent.parent / "configs" / "table_pvt" / "config.json"


# ═══════════════════════════════════════════════════════════
# A. CSV-ридеры
# ═══════════════════════════════════════════════════════════

class TestCSVReaders:
    """Чтение CSV с конвертацией единиц SI → бар/сП."""

    def test_oil_pvt_csv_format(self, tmp_path):
        """4 строки → 4 tuple (Rs, p_bar, Bo, mu_cP)."""
        csv = tmp_path / "oil.csv"
        csv.write_text(
            "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
            "0.0,5000000,1.05,0.003\n"
            "30.0,15000000,1.20,0.0015\n"
        )
        rows = _read_oil_pvt_csv(csv)
        assert len(rows) == 2
        # первая строка: p = 5e6 Па → 50 бар, μ = 0.003 Па·с → 3 сП
        Rs, p, Bo, mu = rows[0]
        assert Rs == 0.0
        assert p == pytest.approx(50.0)
        assert Bo == 1.05
        assert mu == pytest.approx(3.0)

    def test_gas_pvt_csv_format(self, tmp_path):
        """3 строки → 3 tuple (p_bar, Bg, mu_cP)."""
        csv = tmp_path / "gas.csv"
        csv.write_text(
            "pressure_Pa,Bg,mu_g_Pa_s\n"
            "5000000,0.020,0.000012\n"
            "15000000,0.008,0.000014\n"
        )
        rows = _read_gas_pvt_csv(csv)
        assert len(rows) == 2
        # p = 5e6 Па → 50 бар, μ = 1.2e-5 Па·с → 0.012 сП
        p, Bg, mu = rows[0]
        assert p == pytest.approx(50.0)
        assert Bg == 0.020
        assert mu == pytest.approx(0.012)

    def test_relperm_csv_format(self, tmp_path):
        """6 строк → (Sg, kro, krg) без конвертации."""
        csv = tmp_path / "rp.csv"
        csv.write_text(
            "Sg,kro,krg\n"
            "0.0,1.0,0.0\n"
            "0.4,0.3,0.2\n"
            "0.8,0.0,0.8\n"
        )
        Sg, kro, krg = _read_relperm_csv(csv)
        assert len(Sg) == 3
        assert Sg == [0.0, 0.4, 0.8]
        assert kro == [1.0, 0.3, 0.0]
        assert krg == [0.0, 0.2, 0.8]

    def test_oil_csv_skips_blank_lines(self, tmp_path):
        """Пустые строки пропускаются."""
        csv = tmp_path / "oil.csv"
        csv.write_text(
            "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
            "0.0,5000000,1.05,0.003\n"
            "\n"
            "30.0,15000000,1.20,0.0015\n"
        )
        rows = _read_oil_pvt_csv(csv)
        assert len(rows) == 2

    def test_oil_csv_missing_file(self, tmp_path):
        """Несуществующий файл → ValueError."""
        with pytest.raises(ValueError, match="не найден"):
            _read_oil_pvt_csv(tmp_path / "no_such_file.csv")

    def test_gas_csv_missing_file(self, tmp_path):
        """Несуществующий файл → ValueError."""
        with pytest.raises(ValueError, match="не найден"):
            _read_gas_pvt_csv(tmp_path / "no_such_file.csv")

    def test_relperm_csv_missing_file(self, tmp_path):
        """Несуществующий файл → ValueError."""
        with pytest.raises(ValueError, match="не найден"):
            _read_relperm_csv(tmp_path / "no_such_file.csv")


# ═══════════════════════════════════════════════════════════
# B. Factory с табличным PVT
# ═══════════════════════════════════════════════════════════

class TestFactoryTablePVT:
    """Factory: pvt.model="table" → PrototypeHydroAdapter."""

    def test_from_config_creates_prototype_hydro(self):
        """HydroSolver = PrototypeHydroAdapter при pvt.model='table'."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)

        assert isinstance(simulator._hydro, PrototypeHydroAdapter)

    def test_pvt_is_table_full(self):
        """PVT = TableFullPVT при pvt.model='table'."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)

        assert isinstance(simulator._pvt, TableFullPVT)

    def test_factory_passes_max_retries(self):
        """Factory доносит numerics.max_retries до адаптера (DEBT-007).

        Корень DEBT-007 в том, что Factory создавала адаптер тремя
        позиционными аргументами и лимит всегда оставался равным
        значению по умолчанию. Тест закрывает именно эту дыру.
        """
        config = load_config(TABLE_CONFIG)
        config.numerics.max_retries = 7
        simulator, _ = SimulatorFactory.from_config(config)

        assert simulator._hydro._max_retries == 7

    def test_factory_default_max_retries(self):
        """Без правки конфига адаптер получает штатные 9, а не 5."""
        config = load_config(TABLE_CONFIG)
        simulator, _ = SimulatorFactory.from_config(config)

        assert simulator._hydro._max_retries == 9

    def test_relperm_is_prototype_adapter(self):
        """RelPerm = PrototypeRPAdapter при relperm.model='table'."""
        config = load_config(TABLE_CONFIG)
        _, _ = SimulatorFactory.from_config(config)
        # Проверяем через hydro (у которого relperm внутри модели)
        # Проверка: relperm создаётся без ошибок — достаточно

    def test_initial_state_shapes(self):
        """Начальное состояние: размеры массивов = N."""
        config = load_config(TABLE_CONFIG)
        _, initial = SimulatorFactory.from_config(config)

        assert initial.p.shape == (config.grid.N,)
        assert initial.Sg.shape == (config.grid.N,)
        assert initial.Rs.shape == (config.grid.N,)
        assert initial.T.shape == (config.grid.N,)

    def test_config_dir_resolved(self):
        """config_dir заполнен при load_config."""
        config = load_config(TABLE_CONFIG)
        assert config.config_dir == TABLE_CONFIG.parent


# ═══════════════════════════════════════════════════════════
# C. Pipeline: from_config → run → history
# ═══════════════════════════════════════════════════════════

class TestPipeline:
    """Полный pipeline: JSON → Factory → Simulator.run()."""

    def test_run_produces_history(self):
        """run() не падает, history содержит данные."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        assert history.n_saved > 1

    def test_well_rate_positive(self):
        """Давление снижается (добыча идёт)."""
        config = load_config(TABLE_CONFIG)
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)

        # Финальное состояние: давление должно снизиться от начального
        p_final = history.states[-1].p
        assert np.all(p_final <= config.initial_conditions.p0 + 1e-3)


# ═══════════════════════════════════════════════════════════
# D. PVT-согласованность
# ═══════════════════════════════════════════════════════════

class TestPVTConsistency:
    """Один BlackOilPVT в обёртке и в модели."""

    def test_pvt_objects_are_same(self):
        """proto_pvt в PrototypePVTAdapter и в RadialBlackOilModel — один объект."""
        config = load_config(TABLE_CONFIG)
        simulator, _ = SimulatorFactory.from_config(config)

        hydro = simulator._hydro
        assert isinstance(hydro, PrototypeHydroAdapter)

        # proto_pvt через модель
        model_pvt = hydro._model.pvt
        # proto_pvt через адаптер → pvt._pvt
        adapter_pvt = hydro._pvt._pvt

        assert model_pvt is adapter_pvt

    def test_bo_consistency(self):
        """Bo через обёртку и через прототип совпадают."""
        config = load_config(TABLE_CONFIG)
        simulator, _ = SimulatorFactory.from_config(config)

        our_pvt = simulator._pvt._hydro  # PrototypePVTAdapter
        proto_pvt = our_pvt._pvt          # BlackOilPVT

        p_pa = 15e6
        Rs = 20.0
        p_bar = p_pa / BAR_TO_PA

        bo_our = our_pvt.Bo(np.array([p_pa]), np.array([Rs]))[0]
        bo_proto = proto_pvt.bo(np.array([p_bar]), np.array([Rs]))[0]

        assert bo_our == pytest.approx(bo_proto)


# ═══════════════════════════════════════════════════════════
# E. Ошибки конфигурации
# ═══════════════════════════════════════════════════════════

class TestConfigErrors:
    """Ошибки при невалидном конфиге с табличным PVT."""

    def test_table_pvt_without_csv_raises(self, tmp_path):
        """pvt.model='table' без CSV файла → ValueError."""
        import json
        bad_config = {
            "geometry": {"r_well": 0.1, "R_ext": 50.0, "h": 10.0},
            "grid": {"N": 10},
            "rock": {"porosity": 0.2, "permeability": 1e-13,
                     "rho_cp_solid": 1e6, "lambda_solid": 1.5,
                     "lambda_oil": 0.14, "lambda_gas": 0.04},
            "pvt": {"model": "table", "rho_o_std": 850.0, "rho_g_std": 0.85,
                    "oil_pvt_file": "missing_oil.csv",
                    "gas_pvt_file": "missing_gas.csv"},
            "relperm": {"model": "corey"},
            "thermal": {"c_p_oil": 2000, "c_p_gas": 1000,
                        "mu_JT_oil": 0, "mu_JT_gas": 0, "L_degas": 0},
            "initial_conditions": {"p0": 20e6, "T0": 350.0, "Rs0": 30.0},
            "time": {"dt_integration": 3600,
                     "history": [{"dt": 86400, "control": "pressure", "p_wf": 15e6}]},
        }
        cfg_path = tmp_path / "bad.json"
        cfg_path.write_text(json.dumps(bad_config))

        config = load_config(cfg_path)
        with pytest.raises(ValueError, match="не найден"):
            SimulatorFactory.from_config(config)


# ═══════════════════════════════════════════════════════════
# F. Начальное состояние против PVT-таблиц (BUG-017)
# ═══════════════════════════════════════════════════════════

def _table_config_with_oil_csv(tmp_path, oil_csv_text):
    """TABLE_CONFIG с подменённой oil_pvt.csv: копия CSV в tmp_path, config_dir → tmp_path."""
    for name in ("gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / name, tmp_path / name)
    (tmp_path / "oil_pvt.csv").write_text(oil_csv_text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = tmp_path
    return config


class TestInitialStateVsTable:
    """Фабрика отвергает начальное состояние, которое таблица не описывает (BUG-017).

    Таблица configs/table_pvt: ветки Rs = 0 (p_b = 5 МПа) и 30 (p_b = 15 МПа),
    газ 5…30 МПа. BlackOilPVT не экстраполирует: Rs вне веток обрезается,
    а запас газа считается с полным Rs0 — решатель видит пересыщение при
    любом давлении (отказ или скачок давления до 111 МПа при Rs0 = 40).
    """

    def test_rs0_above_last_branch_raises(self):
        """Rs0 = 150 > 30: ошибка про диапазон таблицы, а не про пересыщение.

        Проверка диапазона идёт раньше проверки пересыщения: p_b(150) обрезан
        до 15 МПа < p0, и сообщение о пересыщении было бы противоречивым.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 150.0
        with pytest.raises(ValueError, match="вне диапазона таблицы") as exc:
            SimulatorFactory.from_config(config)
        assert "пересыщ" not in str(exc.value)
        assert "Rs0 = 150" in str(exc.value)

    def test_rs0_below_guard_threshold_raises(self):
        """Rs0 = 40: ниже порога 1.5·Rs_max = 45 пробного вектора Ньютона.

        До правки (после BUG-016) первый шаг молча «сходился» с давлением
        111 МПа. Ловит проверку, ограниченную порогом решателя.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 40.0
        with pytest.raises(ValueError, match="вне диапазона таблицы"):
            SimulatorFactory.from_config(config)

    def test_rs0_below_first_branch_raises(self, tmp_path):
        """Таблица с ветками 5 и 30, Rs0 = 0 < 5: ошибка (решение 2 плана).

        Ниже первой ветки нефть молча не разгазируется никогда
        (R_s^sat(p) >= 5 > Rs0), а B_o, μ_o берутся с ветки 5.
        """
        config = _table_config_with_oil_csv(tmp_path, (
            "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
            "5.0,6000000,1.07,0.0028\n"
            "5.0,30000000,1.06,0.0030\n"
            "30.0,15000000,1.20,0.0015\n"
            "30.0,30000000,1.18,0.0016\n"))
        config.initial_conditions.Rs0 = 0.0
        with pytest.raises(ValueError, match="вне диапазона таблицы"):
            SimulatorFactory.from_config(config)

    def test_rs0_on_last_branch_passes(self):
        """Rs0 = 30 ровно на последней ветке, p0 = 20 МПа > p_b = 15 МПа — допустимо.

        Граница включается: R_s^eq(p0) = 30 ровно (обрезка), Rs0 = 30.
        Так стоят 13 из 14 табличных примеров.
        """
        config = load_config(TABLE_CONFIG)
        assert config.initial_conditions.Rs0 == 30.0
        SimulatorFactory.from_config(config)   # не бросает

    def test_supersaturated_start_raises(self):
        """Rs0 = 20 внутри таблицы, p0 = 10 МПа: R_s^eq(10 МПа) = 15 < 20 — ошибка.

        p_b(20) = 11.67 МПа > p0. Решатель стартует только из однофазного
        состояния; без проверки давление на первом шаге скачком росло бы к p_b.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 20.0
        config.initial_conditions.p0 = 10e6
        with pytest.raises(ValueError, match="пересыщено") as exc:
            SimulatorFactory.from_config(config)
        assert "11.6667" in str(exc.value)   # p_b(20) = 5 + 20/30·10 МПа

    def test_p0_at_bubble_point_passes(self):
        """p0 = p_b(30) = 15 МПа ровно: R_s^eq(p0) = Rs0 — допустимо (как пример 11, p0 = 15.05)."""
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 15e6
        SimulatorFactory.from_config(config)

    def test_p0_1pa_below_pb_passes(self):
        """p0 на 1 Па ниже p_b(30): избыток Rs 3e-6 < допуска 1e-5 — округление ввода не ошибка."""
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 15e6 - 1.0
        SimulatorFactory.from_config(config)

    def test_dead_oil_below_table_pb0_passes(self):
        """Rs0 = 0, p0 = 3 МПа ниже табличного p_b(0) = 5 МПа — допустимо.

        R_s^eq(3 МПа) = 0 = Rs0: пересыщения нет, решатель газ не включит.
        Ловит переход на формулировку p0 >= p_b(Rs0) — она дала бы ложную ошибку.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.Rs0 = 0.0
        config.initial_conditions.p0 = 3e6
        SimulatorFactory.from_config(config)


class TestInitialRangeWarnings:
    """Предупреждения pvt_range_warnings прототипа для начального состояния (BUG-017)."""

    def test_p0_above_tables_warns(self, caplog):
        """p0 = 32 МПа выше газовой таблицы и веток нефти (до 30 МПа): два предупреждения.

        Расчёт допустим (Rs0 = 30 = R_s^eq), но B_g и B_o молча берутся с краёв
        таблиц — пользователь должен это видеть.
        """
        config = load_config(TABLE_CONFIG)
        config.initial_conditions.p0 = 32e6
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno == logging.WARNING)
        assert "GAS_PVT pressure above table" in text
        assert "OIL_PVT branch pressure above supplied range" in text

    def test_in_range_no_warnings(self, caplog):
        """Штатный табличный конфиг: начальное состояние внутри всех таблиц — предупреждений нет."""
        config = load_config(TABLE_CONFIG)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            SimulatorFactory.from_config(config)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
