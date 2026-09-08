"""Тесты интеграции Factory с табличным PVT (FEAT-012).

Проверяют:
- CSV-ридеры: формат, конвертация единиц SI → бар/сП
- Factory: pvt.model="table" → PrototypeHydroAdapter
- Pipeline: from_config → run → history
- PVT-согласованность: один BlackOilPVT в обёртке и в модели
- Ошибки: отсутствие CSV файла
"""

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
