"""Тесты для io/config.py (фаза 3).

Проверяет:
- Чтение baseline.json — все поля, значения, defaults.
- Валидацию: отсутствующие секции, невалидные значения.
- Опциональные секции: numerics, output — defaults при отсутствии.
- История: несколько интервалов, control type, p_wf.
- Минимальный конфиг: только обязательные секции.
"""

import json
import pytest
from pathlib import Path

from gpn_multiphase_solver.io.config import (
    load_config, SimulationConfig,
    GeometryConfig, GridConfig, RockConfig, PVTConfig,
    RelPermConfig, ThermalConfig, InitialConfig,
    TimeConfig, HistoryInterval, NumericsConfig, OutputConfig,
)

BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"


# ═════════════════════════════════════════════════════════════
# A. Чтение baseline.json — все поля и значения
# ═════════════════════════════════════════════════════════════

@pytest.fixture
def cfg():
    return load_config(BASELINE)


class TestBaselineGeometry:
    def test_r_well(self, cfg):
        assert cfg.geometry.r_well == 0.1

    def test_R_ext(self, cfg):
        assert cfg.geometry.R_ext == 50.0

    def test_h(self, cfg):
        assert cfg.geometry.h == 10.0


class TestBaselineGrid:
    def test_N(self, cfg):
        assert cfg.grid.N == 100

    def test_type(self, cfg):
        assert cfg.grid.type == "log_radial"


class TestBaselineRock:
    def test_porosity(self, cfg):
        assert cfg.rock.porosity == 0.2

    def test_permeability(self, cfg):
        assert cfg.rock.permeability == 1e-13

    def test_rho_cp_solid(self, cfg):
        assert cfg.rock.rho_cp_solid == 1.25e6

    def test_lambda_solid(self, cfg):
        assert cfg.rock.lambda_solid == 1.5

    def test_lambda_oil(self, cfg):
        assert cfg.rock.lambda_oil == 0.14

    def test_lambda_gas(self, cfg):
        assert cfg.rock.lambda_gas == 0.04


class TestBaselinePVT:
    def test_model(self, cfg):
        assert cfg.pvt.model == "standing"

    def test_rho_o_std(self, cfg):
        assert cfg.pvt.rho_o_std == 850.0

    def test_rho_g_std(self, cfg):
        assert cfg.pvt.rho_g_std == 0.85

    def test_co_default(self, cfg):
        """co_undersaturated не задан в JSON → default = 0."""
        assert cfg.pvt.co_undersaturated == 0.0


class TestBaselineRelPerm:
    def test_model(self, cfg):
        assert cfg.relperm.model == "corey"

    def test_S_or(self, cfg):
        assert cfg.relperm.S_or == 0.2

    def test_S_gc(self, cfg):
        assert cfg.relperm.S_gc == 0.05

    def test_n_o(self, cfg):
        assert cfg.relperm.n_o == 2.0

    def test_n_g(self, cfg):
        assert cfg.relperm.n_g == 2.0

    def test_kro_max(self, cfg):
        assert cfg.relperm.kro_max == 1.0

    def test_krg_max(self, cfg):
        assert cfg.relperm.krg_max == 0.8


class TestBaselineThermal:
    def test_c_p_oil(self, cfg):
        assert cfg.thermal.c_p_oil == 2000.0

    def test_c_p_gas(self, cfg):
        assert cfg.thermal.c_p_gas == 1000.0

    def test_mu_JT_oil(self, cfg):
        assert cfg.thermal.mu_JT_oil == 4.0e-7

    def test_mu_JT_gas(self, cfg):
        assert cfg.thermal.mu_JT_gas == -4.0e-6

    def test_L_degas(self, cfg):
        assert cfg.thermal.L_degas == 168000.0


class TestBaselineInitialConditions:
    def test_p0(self, cfg):
        assert cfg.initial_conditions.p0 == 20e6

    def test_T0(self, cfg):
        assert cfg.initial_conditions.T0 == 350.0

    def test_Rs0(self, cfg):
        assert cfg.initial_conditions.Rs0 == 50.0


class TestBaselineTime:
    def test_dt_integration(self, cfg):
        assert cfg.time.dt_integration == 3600

    def test_start_day(self, cfg):
        assert cfg.time.start_day == 0.0

    def test_history_count(self, cfg):
        assert len(cfg.time.history) == 2

    def test_history_0_dt(self, cfg):
        assert cfg.time.history[0].dt == 86400

    def test_history_0_control(self, cfg):
        assert cfg.time.history[0].control == "pressure"

    def test_history_0_p_wf(self, cfg):
        assert cfg.time.history[0].p_wf == 15e6

    def test_history_1_dt(self, cfg):
        assert cfg.time.history[1].dt == 259200

    def test_history_1_p_wf(self, cfg):
        assert cfg.time.history[1].p_wf == 10e6


class TestBaselineNumerics:
    def test_dt_min(self, cfg):
        assert cfg.numerics.dt_min == 1.0

    def test_dt_max_default(self, cfg):
        """dt_max не задан в baseline → default = 86400."""
        assert cfg.numerics.dt_max == 86400.0

    def test_skin(self, cfg):
        assert cfg.numerics.skin == 0.0


class TestBaselineOutput:
    def test_log_level(self, cfg):
        assert cfg.output.log_level == "INFO"

    def test_format(self, cfg):
        assert cfg.output.format == "npz"

    def test_save_every(self, cfg):
        assert cfg.output.save_every == 1


class TestConfigTypes:
    """Проверка типов возвращаемых объектов."""

    def test_config_type(self, cfg):
        assert isinstance(cfg, SimulationConfig)

    def test_geometry_type(self, cfg):
        assert isinstance(cfg.geometry, GeometryConfig)

    def test_history_interval_type(self, cfg):
        assert isinstance(cfg.time.history[0], HistoryInterval)


# ═════════════════════════════════════════════════════════════
# B. Опциональные секции — defaults
# ═════════════════════════════════════════════════════════════

def _write_json(tmp_path, data):
    """Записать словарь в JSON-файл и вернуть путь."""
    p = tmp_path / "test.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _minimal_raw():
    """Минимальный валидный конфиг (все обязательные секции)."""
    return {
        "geometry": {"r_well": 0.1, "R_ext": 50.0, "h": 10.0},
        "grid": {"N": 10},
        "rock": {"porosity": 0.2, "permeability": 1e-13},
        "pvt": {"model": "standing", "rho_o_std": 850.0, "rho_g_std": 0.85},
        "relperm": {"model": "corey"},
        "thermal": {},
        "initial_conditions": {"p0": 20e6, "T0": 350.0, "Rs0": 50.0},
        "time": {
            "dt_integration": 3600,
            "history": [{"dt": 86400, "control": "pressure", "p_wf": 10e6}],
        },
    }


class TestOptionalSections:
    """numerics и output отсутствуют → defaults."""

    def test_no_numerics_uses_defaults(self, tmp_path):
        raw = _minimal_raw()
        # numerics и output не заданы
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.newton_max_iter == 15
        assert cfg.numerics.dt_min == 1.0

    def test_no_output_uses_defaults(self, tmp_path):
        raw = _minimal_raw()
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.output.log_level == "INFO"
        assert cfg.output.save_every == 1


class TestMinimalConfig:
    """Минимальный конфиг загружается без ошибок."""

    def test_loads_ok(self, tmp_path):
        raw = _minimal_raw()
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.geometry.r_well == 0.1
        assert cfg.grid.N == 10
        assert len(cfg.time.history) == 1


# ═════════════════════════════════════════════════════════════
# C. Валидация — отсутствующие секции
# ═════════════════════════════════════════════════════════════

class TestMissingSections:
    """Отсутствие обязательной секции → ValueError."""

    @pytest.mark.parametrize("section", [
        "geometry", "grid", "rock", "pvt", "relperm",
        "thermal", "initial_conditions", "time",
    ])
    def test_missing_section_raises(self, tmp_path, section):
        raw = _minimal_raw()
        del raw[section]
        with pytest.raises(ValueError, match=section):
            load_config(_write_json(tmp_path, raw))


# ═════════════════════════════════════════════════════════════
# D. Валидация — невалидные значения
# ═════════════════════════════════════════════════════════════

class TestValidationGeometry:
    def test_r_well_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["geometry"]["r_well"] = 0
        with pytest.raises(ValueError, match="r_well"):
            load_config(_write_json(tmp_path, raw))

    def test_r_well_negative(self, tmp_path):
        raw = _minimal_raw()
        raw["geometry"]["r_well"] = -0.1
        with pytest.raises(ValueError, match="r_well"):
            load_config(_write_json(tmp_path, raw))

    def test_R_ext_less_than_r_well(self, tmp_path):
        raw = _minimal_raw()
        raw["geometry"]["R_ext"] = 0.05  # меньше r_well=0.1
        with pytest.raises(ValueError, match="R_ext"):
            load_config(_write_json(tmp_path, raw))

    def test_h_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["geometry"]["h"] = 0
        with pytest.raises(ValueError, match="h"):
            load_config(_write_json(tmp_path, raw))


class TestValidationGrid:
    def test_N_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["grid"]["N"] = 0
        with pytest.raises(ValueError, match="N"):
            load_config(_write_json(tmp_path, raw))


class TestValidationRock:
    def test_porosity_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["rock"]["porosity"] = 0
        with pytest.raises(ValueError, match="porosity"):
            load_config(_write_json(tmp_path, raw))

    def test_porosity_over_one(self, tmp_path):
        raw = _minimal_raw()
        raw["rock"]["porosity"] = 1.5
        with pytest.raises(ValueError, match="porosity"):
            load_config(_write_json(tmp_path, raw))

    def test_permeability_negative(self, tmp_path):
        raw = _minimal_raw()
        raw["rock"]["permeability"] = -1e-13
        with pytest.raises(ValueError, match="permeability"):
            load_config(_write_json(tmp_path, raw))


class TestValidationInitial:
    def test_p0_negative(self, tmp_path):
        raw = _minimal_raw()
        raw["initial_conditions"]["p0"] = -1e6
        with pytest.raises(ValueError, match="p0"):
            load_config(_write_json(tmp_path, raw))

    def test_T0_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["initial_conditions"]["T0"] = 0
        with pytest.raises(ValueError, match="T0"):
            load_config(_write_json(tmp_path, raw))

    def test_Rs0_negative(self, tmp_path):
        raw = _minimal_raw()
        raw["initial_conditions"]["Rs0"] = -10
        with pytest.raises(ValueError, match="Rs0"):
            load_config(_write_json(tmp_path, raw))


class TestValidationTime:
    def test_dt_integration_zero(self, tmp_path):
        raw = _minimal_raw()
        raw["time"]["dt_integration"] = 0
        with pytest.raises(ValueError, match="dt_integration"):
            load_config(_write_json(tmp_path, raw))

    def test_empty_history(self, tmp_path):
        raw = _minimal_raw()
        raw["time"]["history"] = []
        with pytest.raises(ValueError, match="history"):
            load_config(_write_json(tmp_path, raw))

    def test_history_dt_negative(self, tmp_path):
        raw = _minimal_raw()
        raw["time"]["history"][0]["dt"] = -1
        with pytest.raises(ValueError, match="dt"):
            load_config(_write_json(tmp_path, raw))

    def test_pressure_control_without_p_wf(self, tmp_path):
        """control='pressure', но p_wf не задано → ошибка."""
        raw = _minimal_raw()
        del raw["time"]["history"][0]["p_wf"]
        with pytest.raises(ValueError, match="p_wf"):
            load_config(_write_json(tmp_path, raw))

    def test_pressure_control_p_wf_negative(self, tmp_path):
        raw = _minimal_raw()
        raw["time"]["history"][0]["p_wf"] = -5e6
        with pytest.raises(ValueError, match="p_wf"):
            load_config(_write_json(tmp_path, raw))


# ═════════════════════════════════════════════════════════════
# E. Мульти-интервальная история
# ═════════════════════════════════════════════════════════════

class TestMultiInterval:
    """Несколько интервалов с разными p_wf."""

    def test_three_intervals(self, tmp_path):
        raw = _minimal_raw()
        raw["time"]["history"] = [
            {"dt": 86400, "control": "pressure", "p_wf": 18e6},
            {"dt": 172800, "control": "pressure", "p_wf": 15e6},
            {"dt": 604800, "control": "pressure", "p_wf": 10e6},
        ]
        cfg = load_config(_write_json(tmp_path, raw))
        assert len(cfg.time.history) == 3
        assert cfg.time.history[0].p_wf == 18e6
        assert cfg.time.history[1].p_wf == 15e6
        assert cfg.time.history[2].p_wf == 10e6
        # Длительности
        assert cfg.time.history[0].dt == 86400
        assert cfg.time.history[1].dt == 172800
        assert cfg.time.history[2].dt == 604800


class TestHistoryIntervalDefaults:
    """Defaults для HistoryInterval."""

    def test_control_default_pressure(self, tmp_path):
        raw = _minimal_raw()
        # control не задан явно → default "pressure"
        raw["time"]["history"] = [{"dt": 86400, "p_wf": 10e6}]
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.time.history[0].control == "pressure"

    def test_q_total_default_none(self, tmp_path):
        raw = _minimal_raw()
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.time.history[0].q_total is None
