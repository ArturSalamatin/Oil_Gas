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

    def test_mu_o_undersaturated_default(self, cfg):
        """mu_o_undersaturated не задан в JSON → "none": старые конфиги прежние (FEAT-027)."""
        assert cfg.pvt.mu_o_undersaturated == "none"

    def test_mu_o_undersaturated_read(self, tmp_path):
        """Значение "beal" из секции pvt доходит до PVTConfig (FEAT-027)."""
        raw = _minimal_raw()
        raw["pvt"]["mu_o_undersaturated"] = "beal"
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.pvt.mu_o_undersaturated == "beal"


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
        # μ_JT = (∂T/∂p)_h (eq:muJT_def): у нефти < 0 — при дросселировании греется
        assert cfg.thermal.mu_JT_oil == -4.0e-7

    def test_mu_JT_gas(self, cfg):
        # у газа > 0 — при дросселировании охлаждается
        assert cfg.thermal.mu_JT_gas == 4.0e-6

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

    # Сценарий baseline: сутки при 15 МПа, затем трое суток при 10 МПа.
    # После DEBT-013 он записан 96 интервалами по 3600 с (24 + 72), потому
    # что частоту вывода задаёт только структура истории. Проверяем сам
    # сценарий — длительность и режим каждого этапа, а не разбиение:
    # число интервалов зависит от желаемого шага записи и может меняться.

    def test_history_count(self, cfg):
        """24 часа при 15 МПа + 72 часа при 10 МПа."""
        assert len(cfg.time.history) == 96

    def test_history_step_uniform(self, cfg):
        """Шаг записи одинаков во всех интервалах — 1 час."""
        assert {h.dt for h in cfg.time.history} == {3600.0}

    def test_history_control_is_pressure(self, cfg):
        assert {h.control for h in cfg.time.history} == {"pressure"}

    def test_history_stage_1(self, cfg):
        """Первый этап: сутки при p_wf = 15 МПа."""
        stage = [h for h in cfg.time.history if h.p_wf == 15e6]
        assert sum(h.dt for h in stage) == 86400

    def test_history_stage_2(self, cfg):
        """Второй этап: трое суток при p_wf = 10 МПа."""
        stage = [h for h in cfg.time.history if h.p_wf == 10e6]
        assert sum(h.dt for h in stage) == 259200


class TestBaselineNumerics:
    def test_dt_min(self, cfg):
        assert cfg.numerics.dt_min == 1.0

    def test_dt_max_default(self, cfg):
        """dt_max не задан в baseline → default = 86400."""
        assert cfg.numerics.dt_max == 86400.0

    def test_skin(self, cfg):
        assert cfg.numerics.skin == 0.0

    def test_max_retries_default(self, cfg):
        """max_retries не задан в baseline → default = 9.

        Значение — измеренный порог примера 03 при двух отягчающих
        факторах (N = 75, p_wf = 6 МПа); см. DEBT-007.
        """
        assert cfg.numerics.max_retries == 9


class TestBaselineOutput:
    def test_log_level(self, cfg):
        assert cfg.output.log_level == "INFO"

    def test_format(self, cfg):
        assert cfg.output.format == "npz"

    def test_save_every_rejected(self, tmp_path):
        """Старый конфиг с save_every отвергается с объяснением (DEBT-013).

        Молча игнорировать поле нельзя: пользователь рассчитывает на
        прореживание вывода, а его больше нет — состав истории изменился
        бы без предупреждения. Без явной проверки строгая распаковка
        dataclass дала бы невнятный TypeError про лишний аргумент.
        """
        raw = _minimal_raw()
        raw["output"] = {"log_level": "INFO", "save_every": 12}
        with pytest.raises(ValueError, match="save_every"):
            load_config(_write_json(tmp_path, raw))


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
        assert cfg.numerics.max_retries == 9

    def test_no_output_uses_defaults(self, tmp_path):
        raw = _minimal_raw()
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.output.log_level == "INFO"
        assert cfg.output.format == "npz"


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

    # ── Управление по дебиту нефти (FEAT-020) ──
    # Каждый интервал задаёт ровно одно управление; поля другого управления
    # отвергаются как мёртвые (DEBT-008), иначе пользователь решит, что они
    # на что-то влияют.

    @pytest.mark.parametrize("interval, field", [
        # неизвестное управление: прежде проходило валидацию и падало в фабрике
        ({"dt": 86400, "control": "rat", "p_wf": 10e6}, "control"),
        # rate без дебита
        ({"dt": 86400, "control": "rate", "min_bhp": 1e5}, "q_oil"),
        # rate без нижней границы p_wf: при λ_o -> 0 p_wf ушло бы в -inf
        ({"dt": 86400, "control": "rate", "q_oil": 1e-3}, "min_bhp"),
        # отрицательный дебит — нагнетание, прототип его не поддерживает
        ({"dt": 86400, "control": "rate", "q_oil": -1e-3, "min_bhp": 1e5}, "q_oil"),
        ({"dt": 86400, "control": "rate", "q_oil": 1e-3, "min_bhp": 0.0}, "min_bhp"),
        # p_wf при заданном дебите вычисляется, задавать его — ошибка
        ({"dt": 86400, "control": "rate", "q_oil": 1e-3, "min_bhp": 1e5,
          "p_wf": 10e6}, "p_wf"),
        # поля управления по дебиту при управлении по давлению не читаются
        ({"dt": 86400, "control": "pressure", "p_wf": 10e6, "q_oil": 1e-3}, "q_oil"),
        ({"dt": 86400, "control": "pressure", "p_wf": 10e6, "min_bhp": 1e5}, "min_bhp"),
    ], ids=["unknown_control", "rate_without_q_oil", "rate_without_min_bhp",
            "rate_negative_q_oil", "rate_nonpositive_min_bhp",
            "rate_with_p_wf", "pressure_with_q_oil", "pressure_with_min_bhp"])
    def test_rate_control_validation(self, tmp_path, interval, field):
        """Ошибки управления интервала называют поле, в котором они допущены."""
        raw = _minimal_raw()
        raw["time"]["history"] = [interval]
        with pytest.raises(ValueError, match=field):
            load_config(_write_json(tmp_path, raw))


class TestMaxRetriesValidation:
    """Валидация numerics.max_retries — граница и тип (DEBT-007, BUG-003).

    Лимит попадает в показатель степени (2**max_retries), поэтому
    нецелые и отрицательные значения обязаны отсекаться при загрузке,
    а не падать позже внутри адаптера.
    """

    def test_explicit_value_read(self, tmp_path):
        """Значение из JSON доходит до конфига без изменений."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": 7}
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.max_retries == 7

    def test_zero_allowed(self, tmp_path):
        """0 осмыслен: одна попытка без дробления, дробить запрещено."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": 0}
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.max_retries == 0

    def test_upper_bound_allowed(self, tmp_path):
        """20 — верхняя допустимая граница, ещё принимается."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": 20}
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.max_retries == 20

    def test_negative_rejected(self, tmp_path):
        """Отрицательное дало бы range(0) — цикл не выполнится ни разу."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": -1}
        with pytest.raises(ValueError, match="max_retries"):
            load_config(_write_json(tmp_path, raw))

    def test_too_large_rejected(self, tmp_path):
        """2**100 подшагов недостижимо — защита от опечатки."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": 100}
        with pytest.raises(ValueError, match="max_retries"):
            load_config(_write_json(tmp_path, raw))

    def test_float_rejected(self, tmp_path):
        """Дробное дало бы float в range() — TypeError вдали от причины."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": 9.5}
        with pytest.raises(ValueError, match="max_retries"):
            load_config(_write_json(tmp_path, raw))

    def test_bool_rejected(self, tmp_path):
        """bool — подкласс int, но True как лимит бессмыслен."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": True}
        with pytest.raises(ValueError, match="max_retries"):
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

    def test_q_oil_default_none(self, tmp_path):
        # При управлении по давлению дебит не задаётся: поле остаётся None.
        # Имя q_oil (не q_total) — управление идёт по дебиту нефти, FEAT-020.
        raw = _minimal_raw()
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.time.history[0].q_oil is None

    def test_rate_interval_loads(self, tmp_path):
        """Интервал с управлением по дебиту читается как задан (СИ, без пересчёта).

        q_oil — м³ст/с, min_bhp — Па; p_wf при заданном дебите не задаётся.
        """
        raw = _minimal_raw()
        raw["time"]["history"] = [
            {"dt": 86400, "control": "rate", "q_oil": 2.0e-3, "min_bhp": 101325.0}]
        h = load_config(_write_json(tmp_path, raw)).time.history[0]
        assert h.control == "rate"
        assert h.q_oil == 2.0e-3
        assert h.min_bhp == 101325.0
        assert h.p_wf is None


# ═════════════════════════════════════════════════════════════
# F. Краткие формы истории (FEAT-018)
# ═════════════════════════════════════════════════════════════
#
# Объект time.history задаёт время одной из трёх форм:
#   {dt}               — один интервал (исходная форма);
#   {dt, repeat}       — repeat одинаковых интервалов по dt;
#   {duration, dt_out} — этап duration с записью раз в dt_out.
# Парсер разворачивает краткие формы в тот же list[HistoryInterval],
# поэтому решатель о них не знает. Запись — на конце каждого интервала
# (DEBT-013), значит число интервалов = число записей этапа.


def _history_of(tmp_path, history):
    """Загрузить минимальный конфиг с заданной time.history."""
    raw = _minimal_raw()
    raw["time"]["history"] = history
    return load_config(_write_json(tmp_path, raw)).time.history


class TestHistoryBlocks:
    """Разворачивание кратких форм и их валидация."""

    def test_repeat_equals_explicit(self, tmp_path):
        """repeat = 3 даёт ровно тот же список, что три явных объекта."""
        block = _history_of(tmp_path, [{"dt": 3600, "repeat": 3, "p_wf": 10e6}])
        explicit = _history_of(tmp_path, [{"dt": 3600, "p_wf": 10e6}] * 3)
        assert len(block) == 3
        assert block == explicit

    def test_duration_equals_explicit(self, tmp_path):
        """Трое суток с записью раз в сутки — три интервала по 86 400 с."""
        block = _history_of(tmp_path, [
            {"duration": 259200, "dt_out": 86400, "p_wf": 10e6}])
        explicit = _history_of(tmp_path, [{"dt": 86400, "p_wf": 10e6}] * 3)
        assert block == explicit

    def test_stepped_schedule(self, tmp_path):
        """Ступенчатое расписание + явный интервал: порядок и длины сохраняются.

        Первый час по 300 с (12 записей), затем 5 ч по 3600 с (5 записей),
        затем 600 с при другом p_wf. Всего 18 интервалов, 22 200 с.
        """
        h = _history_of(tmp_path, [
            {"duration": 3600, "dt_out": 300, "p_wf": 12e6},
            {"duration": 18000, "dt_out": 3600, "p_wf": 12e6},
            {"dt": 600, "p_wf": 8e6},
        ])
        assert [x.dt for x in h] == [300.0] * 12 + [3600.0] * 5 + [600.0]
        assert [x.p_wf for x in h] == [12e6] * 17 + [8e6]
        assert sum(x.dt for x in h) == 22200.0

    def test_baseline_as_blocks(self, tmp_path):
        """Сценарий baseline.json краткой формой даёт тот же список интервалов.

        baseline — сутки при 15 МПа и трое суток при 10 МПа с записью раз
        в час, 96 явных объектов (DEBT-014). Сам конфиг не меняется
        (решение пользователя): проверяется, что две строки краткой формы
        заменяют 96 объектов без изменения расчёта.
        """
        raw = json.loads(BASELINE.read_text(encoding="utf-8"))
        raw["time"]["history"] = [
            {"dt": 3600, "repeat": 24, "control": "pressure", "p_wf": 15e6},
            {"duration": 259200, "dt_out": 3600,
             "control": "pressure", "p_wf": 10e6},
        ]
        blocks = load_config(_write_json(tmp_path, raw)).time.history
        assert blocks == load_config(BASELINE).time.history

    def test_rate_control_block(self, tmp_path):
        """Поля управления по дебиту переходят во все интервалы блока."""
        h = _history_of(tmp_path, [
            {"duration": 7200, "dt_out": 3600,
             "control": "rate", "q_oil": 2e-3, "min_bhp": 1e5}])
        assert len(h) == 2
        for x in h:
            assert (x.control, x.q_oil, x.min_bhp, x.p_wf) == ("rate", 2e-3, 1e5, None)

    def test_intervals_are_distinct_objects(self, tmp_path):
        """Правка одного интервала не меняет соседей по блоку.

        Тесты и скрипты правят history[k] после загрузки. Общий объект
        в нескольких позициях списка изменил бы весь блок разом.
        """
        h = _history_of(tmp_path, [{"dt": 3600, "repeat": 3, "p_wf": 10e6}])
        h[0].p_wf = 5e6
        assert [x.p_wf for x in h] == [5e6, 10e6, 10e6]

    def test_decimal_rounding_accepted(self, tmp_path):
        """0.3 / 0.1 = 2.9999999999999996 в двоичной арифметике — это кратность.

        Допуск поглощает округление десятичной записи; без него корректный
        конфиг отвергался бы как некратный.
        """
        h = _history_of(tmp_path, [{"duration": 0.3, "dt_out": 0.1, "p_wf": 10e6}])
        assert len(h) == 3

    @pytest.mark.parametrize("entry, pattern", [
        # некратность: последний момент записи сдвинулся бы (решение пользователя)
        ({"duration": 10000, "dt_out": 3600, "p_wf": 10e6},
         r"history\[0\]: duration .* не кратна"),
        # шаг записи длиннее этапа — та же некратность, отношение < 1
        ({"duration": 100, "dt_out": 300, "p_wf": 10e6}, r"не кратна"),
        ({"duration": 0, "dt_out": 300, "p_wf": 10e6}, r"history\[0\]\.duration"),
        ({"duration": 3600, "dt_out": -300, "p_wf": 10e6}, r"history\[0\]\.dt_out"),
        # неполные и смешанные наборы полей времени
        ({"duration": 3600, "p_wf": 10e6}, r"неверный набор полей времени"),
        ({"dt_out": 300, "p_wf": 10e6}, r"неверный набор полей времени"),
        ({"repeat": 3, "p_wf": 10e6}, r"неверный набор полей времени"),
        ({"dt": 300, "duration": 3600, "dt_out": 300, "p_wf": 10e6},
         r"неверный набор полей времени"),
        ({"dt": 300, "dt_out": 300, "p_wf": 10e6}, r"неверный набор полей времени"),
        ({"p_wf": 10e6}, r"неверный набор полей времени"),
        # repeat идёт в range(): только целое >= 1, bool исключён
        ({"dt": 300, "repeat": 0, "p_wf": 10e6}, r"history\[0\]\.repeat"),
        ({"dt": 300, "repeat": 2.5, "p_wf": 10e6}, r"history\[0\]\.repeat"),
        ({"dt": 300, "repeat": 72.0, "p_wf": 10e6}, r"history\[0\]\.repeat"),
        ({"dt": 300, "repeat": True, "p_wf": 10e6}, r"history\[0\]\.repeat"),
    ], ids=["not_multiple", "dt_out_exceeds_duration", "duration_zero",
            "dt_out_negative", "duration_without_dt_out", "dt_out_without_duration",
            "repeat_without_dt", "dt_with_duration", "dt_with_dt_out", "no_time_keys",
            "repeat_zero", "repeat_fractional", "repeat_float_integral", "repeat_bool"])
    def test_block_validation(self, tmp_path, entry, pattern):
        """Ошибки формы блока называют объект JSON и поле."""
        with pytest.raises(ValueError, match=pattern):
            _history_of(tmp_path, [entry])

    def test_error_names_block_not_expanded_index(self, tmp_path):
        """Ошибка управления называет номер объекта в JSON, а не развёрнутый.

        Первый объект разворачивается в 5 интервалов, поэтому второй после
        разворачивания стоит под номером 5. Пользователь правит history[1] —
        его и должно назвать сообщение.
        """
        with pytest.raises(ValueError,
                           match=r"history\[1\]: control='pressure', но p_wf") as exc:
            _history_of(tmp_path, [{"dt": 300, "repeat": 5, "p_wf": 10e6},
                                   {"dt": 3600, "control": "pressure"}])
        assert "history[5]" not in str(exc.value)
