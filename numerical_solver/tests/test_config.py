"""Тесты для io/config.py (фаза 3).

Проверяет:
- Чтение baseline.json — все поля, значения, defaults.
- Валидацию: отсутствующие секции, невалидные значения; любое числовое поле —
  число и конечное, с именем поля в отказе (DEBT-051).
- Тепловые параметры: c_p, (ρc_p)_s > 0, λ ≥ 0, предупреждение при L < 0 (DEBT-047);
  L, μ_JT,o, μ_JT,g — конечные, знак любой, предупреждение при μ_JT,o > 0 (DEBT-049).
- numerics.newton_cell_tol: положительное конечное или null (BUG-022).
- time.dt_after_control_change: положительное конечное или null (FEAT-032).
- Опциональные секции: numerics, output — defaults при отсутствии.
- История: несколько интервалов, control type, p_wf.
- Скважина: skin ≥ 0 (отказ с обходом через r_well), предупреждения при skin > 50
  и при p_wf / min_bhp ≥ p0 в объекте истории (DEBT-056); при skin > 0 —
  скин не входит в уравнение энергии (BUG-029).
- Порода: сжимаемость rock.compressibility ≥ 0 (DEBT-068).
- PVT: плотности при ст. у. pvt.rho_o_std, pvt.rho_g_std > 0 при любой модели PVT (DEBT-076).
- Минимальный конфиг: только обязательные секции.
- Мёртвые поля (DEBT-008): удалённые ключи — предупреждение и пропуск; grid.type,
  output.log_level, лимиты и допуски Ньютона — проверка; умолчания = умолчаниям прототипа.
"""

import json
import logging
import pytest
from dataclasses import fields
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

    # Сценарий baseline: сутки при 15 МПа, затем трое суток при 10 МПа.
    # Частоту вывода задаёт только структура истории (DEBT-013): в конфиге
    # два блока {duration, dt_out} (DEBT-014), после разворачивания —
    # 96 интервалов по 3600 с (24 + 72). Проверяем сам сценарий —
    # длительность и режим каждого этапа, а не разбиение: число интервалов
    # зависит от желаемого шага записи и может меняться.

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
    def test_skin(self, cfg):
        assert cfg.numerics.skin == 0.0

    def test_max_retries_default(self, cfg):
        """max_retries не задан в baseline → default = 9.

        Значение — запас над замеренными порогами, а не порог; обоснование —
        комментарий NumericsConfig.max_retries (gpn_multiphase_solver/io/config.py).
        """
        assert cfg.numerics.max_retries == 9


class TestBaselineOutput:
    def test_log_level(self, cfg):
        assert cfg.output.log_level == "INFO"

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
        assert cfg.numerics.max_active_set_iter == 12
        assert cfg.numerics.max_retries == 9

    def test_no_output_uses_defaults(self, tmp_path):
        raw = _minimal_raw()
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.output.log_level == "INFO"


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

    @pytest.mark.parametrize("c_r", [
        # ошибка знака у значения примера 18: расчёт шёл молча, дебит нефти
        # на 1 сут на 6 % ниже, чем при +4.5e-10
        -4.5e-10,
        # между −c_o и 0 (c_o = 1.2e-9 у PVT примера 18): C_p ≥ 0, расчёт
        # шёл молча, дебит на 14 % ниже
        -1e-9,
        # c_r < −c_o: C_p < 0 в недонасыщенной зоне — отказ после дробления
        # шага до dt/512 с советом увеличить max_retries, без имени параметра
        -2e-9,
        # наименьшее по модулю отрицательное число: проверка — по знаку, без допуска
        -5e-324,
    ], ids=["sign_error_example18", "above_minus_c_o", "below_minus_c_o", "tiny"])
    def test_negative_compressibility_rejected(self, tmp_path, c_r):
        """c_r < 0 → ValueError с полным именем поля и значением (DEBT-068).

        c_r = (1/φ)·dφ/dp ≥ 0 (eq:porosity): поровый объём с ростом давления не
        уменьшается; загрузчик книги прототипа c_r < 0 тоже отвергает. Комментарии
        к случаям — замер до DEBT-068 на конфиге примера 18, 2 сут
        (vault/issues/debt-068/probes/red_state.out.txt).
        """
        raw = _minimal_raw()
        raw["rock"]["compressibility"] = c_r
        with pytest.raises(ValueError, match="rock.compressibility") as exc:
            load_config(_write_json(tmp_path, raw))
        # значение — как в конфиге: по нему пользователь найдёт ошибку
        assert f"= {c_r} 1/Па" in str(exc.value)

    @pytest.mark.parametrize("c_r", [0.0, 4.5e-10], ids=["zero_default", "example18"])
    def test_nonnegative_compressibility_accepted(self, tmp_path, c_r):
        """c_r = 0 и 4.5e-10 1/Па проходят: умолчание и значение примера 18.

        Пример 18 — единственный из 31 конфига проекта, где c_r задано.
        """
        raw = _minimal_raw()
        raw["rock"]["compressibility"] = c_r
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.rock.compressibility == c_r


class TestValidationPVT:
    """Плотности при стандартных условиях > 0 (DEBT-076).

    ρ_o,ст, ρ_g,ст входят в энергию (eq:rho_oil, eq:mdot), у Стендинга — и в
    корреляции. Комментарии к случаям — замер до DEBT-076, 2 сут
    (vault/issues/debt-076/probes/density_sign.out.txt, пример 18 — таблица
    PVT; density_sign_standing.out.txt, пример 03 — Стендинг): load_config
    принимал все случаи.
    """

    @pytest.mark.parametrize("model", ["standing", "table"])
    @pytest.mark.parametrize("key, value", [
        # таблица: охлаждение забоя −3.02 К вместо −0.23 К, молча;
        # Стендинг: отказ фабрики «пересыщено газом», p_b(Rs0) = 138025 МПа
        ("rho_o_std", -850.0),
        # таблица: −1.16 К; Стендинг: ZeroDivisionError в _api_gravity
        ("rho_o_std", 0.0),
        # таблица: нагрев +0.56 К вместо охлаждения; Стендинг: «пересыщено газом»
        ("rho_g_std", -0.85),
        # таблица: нагрев +0.16 К; Стендинг: «пересыщено газом», p_b = inf
        ("rho_g_std", 0.0),
        # наименьшее по модулю отрицательное число: проверка по знаку, без допуска
        ("rho_g_std", -5e-324),
    ], ids=["rho_o_negative", "rho_o_zero", "rho_g_negative", "rho_g_zero", "rho_g_tiny"])
    def test_nonpositive_density_rejected(self, tmp_path, key, value, model):
        """ρ ≤ 0 → ValueError в load_config с полным именем поля — при любой модели PVT."""
        raw = _minimal_raw()
        raw["pvt"]["model"] = model
        if model == "table":
            # load_config CSV не читает (их читает фабрика): отказ — до файлов
            raw["pvt"].update(oil_pvt_file="oil_pvt.csv", gas_pvt_file="gas_pvt.csv")
        raw["pvt"][key] = value
        with pytest.raises(ValueError, match=f"pvt.{key}") as exc:
            load_config(_write_json(tmp_path, raw))
        # значение — как в конфиге, смысл поля — чтобы не спутать с пластовой
        assert f"= {value} кг/м³" in str(exc.value)
        assert "при стандартных условиях" in str(exc.value)

    @pytest.mark.parametrize("rho_o, rho_g", [
        (850.0, 0.85), (800.0, 0.727), (800.0, 1.014),
    ], ids=["examples_01_16_18", "examples_19_21", "examples_17_20"])
    def test_project_densities_accepted(self, tmp_path, rho_o, rho_g):
        """Плотности всех 31 конфига проекта проходят: верхней границы и порогов нет."""
        raw = _minimal_raw()
        raw["pvt"].update(rho_o_std=rho_o, rho_g_std=rho_g)
        cfg = load_config(_write_json(tmp_path, raw))
        assert (cfg.pvt.rho_o_std, cfg.pvt.rho_g_std) == (rho_o, rho_g)


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


class TestNewtonCellTolValidation:
    """numerics.newton_cell_tol — порог условия сходимости Ньютона по ячейке (BUG-022).

    Положительное конечное число или null (условие выключено). Фабрика передаёт его
    прототипу (cell_tol); неверное значение отсекается при загрузке, а не в
    конструкторе модели.
    """

    def test_default(self, tmp_path):
        """Без поля — 1e-8 (замер BUG-022)."""
        cfg = load_config(_write_json(tmp_path, _minimal_raw()))
        assert cfg.numerics.newton_cell_tol == 1e-8

    def test_explicit_value_read(self, tmp_path):
        """Значение из JSON доходит до конфига без изменений."""
        raw = _minimal_raw()
        raw["numerics"] = {"newton_cell_tol": 1e-6}
        assert load_config(_write_json(tmp_path, raw)).numerics.newton_cell_tol == 1e-6

    def test_null_disables(self, tmp_path):
        """null — условие выключено (None)."""
        raw = _minimal_raw()
        raw["numerics"] = {"newton_cell_tol": None}
        assert load_config(_write_json(tmp_path, raw)).numerics.newton_cell_tol is None

    @pytest.mark.parametrize("value", [0.0, -1e-8, float("nan"), float("inf"), True, "1e-8"])
    def test_invalid_rejected(self, tmp_path, value):
        """0 и отрицательный невыполнимы, NaN и inf бессмысленны, bool и строка — опечатка типа."""
        raw = _minimal_raw()
        raw["numerics"] = {"newton_cell_tol": value}
        with pytest.raises(ValueError, match="newton_cell_tol"):
            load_config(_write_json(tmp_path, raw))


class TestDtAfterControlChange:
    """time.dt_after_control_change — первый подшаг после смены управления (FEAT-032).

    Положительное конечное число или null (выключено, по умолчанию). Верхней границы
    нет: значение не меньше шага интервала просто выключает нарастание.
    """

    def test_default_none(self, tmp_path):
        """Без поля — None: прежние конфиги считаются как прежде."""
        cfg = load_config(_write_json(tmp_path, _minimal_raw()))
        assert cfg.time.dt_after_control_change is None

    def test_value_read(self, tmp_path):
        """Значение из JSON доходит до конфига без изменений."""
        raw = _minimal_raw()
        raw["time"]["dt_after_control_change"] = 2.0
        assert load_config(_write_json(tmp_path, raw)).time.dt_after_control_change == 2.0

    def test_null_disables(self, tmp_path):
        """null — нарастание выключено (None)."""
        raw = _minimal_raw()
        raw["time"]["dt_after_control_change"] = None
        assert load_config(_write_json(tmp_path, raw)).time.dt_after_control_change is None

    @pytest.mark.parametrize("value", [0.0, -2.0, float("nan"), float("inf"), True, "2"])
    def test_invalid_rejected(self, tmp_path, value):
        """0 и отрицательное бессмысленны, NaN и inf — тоже, bool и строка — опечатка типа."""
        raw = _minimal_raw()
        raw["time"]["dt_after_control_change"] = value
        with pytest.raises(ValueError, match="dt_after_control_change"):
            load_config(_write_json(tmp_path, raw))


class TestValidationThermal:
    """Тепловые параметры (DEBT-047, P8 §5).

    Ошибка в них не роняет расчёт, а даёт правдоподобную, но неверную T.
    Комментарии к случаям — замер до DEBT-047 (vault/issues/debt-047/probes/
    red_state.out.txt: baseline, 24 ч; отклонение — от эталона по всем
    записям и ячейкам): все случаи проходили load_config и run без сообщения.
    """

    @pytest.mark.parametrize("section, key, value", [
        # p_wf = 6 МПа: T_min = 11.8 К при эталоне 349.7 К
        ("thermal", "c_p_oil", 0.0),
        # T_min = −7947 К
        ("thermal", "c_p_oil", -2000.0),
        # NaN проходит `v <= 0` молча; JSON допускает литерал NaN
        ("thermal", "c_p_oil", float("nan")),
        # отказ scipy в СЛАУ энергии без имени параметра
        ("thermal", "c_p_oil", float("inf")),
        # газовая зона: отклонение T 0.06 и 0.13 К
        ("thermal", "c_p_gas", 0.0),
        ("thermal", "c_p_gas", -1000.0),
        # отклонение 0.9 К; при (ρc_p)_s < 0 — T до ±7e42 К, конечна
        ("rock", "rho_cp_solid", 0.0),
        ("rock", "rho_cp_solid", -1.25e6),
        # обратная теплопроводность: отклонение — тысячные доли кельвина
        ("rock", "lambda_solid", -1.5),
        ("rock", "lambda_oil", -0.14),
        ("rock", "lambda_gas", -0.04),
        ("rock", "lambda_solid", float("nan")),
        ("rock", "lambda_solid", float("inf")),
    ], ids=["c_p_oil_zero", "c_p_oil_negative", "c_p_oil_nan", "c_p_oil_inf",
            "c_p_gas_zero", "c_p_gas_negative",
            "rho_cp_solid_zero", "rho_cp_solid_negative",
            "lambda_solid_negative", "lambda_oil_negative", "lambda_gas_negative",
            "lambda_solid_nan", "lambda_solid_inf"])
    def test_invalid_rejected(self, tmp_path, section, key, value):
        """Недопустимое значение → ValueError с полным именем параметра."""
        raw = _minimal_raw()
        raw[section][key] = value
        with pytest.raises(ValueError, match=f"{section}.{key}"):
            load_config(_write_json(tmp_path, raw))

    def test_zero_conductivity_accepted(self, tmp_path):
        """λ = 0 — штатный режим «без теплопроводности» (примеры 01, 02)."""
        raw = _minimal_raw()
        raw["rock"].update(lambda_solid=0.0, lambda_oil=0.0, lambda_gas=0.0)
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.rock.lambda_solid == 0.0

    def test_negative_L_warns(self, tmp_path, caplog):
        """L < 0 — предупреждение, не отказ: физически возможно (P8 §5).

        Q_deg = −L·ṁ: при L < 0 выделение газа нагревает пласт (замер:
        T_max 355.1 К против 352.2 К у эталона при p_wf = 6 МПа).
        """
        raw = _minimal_raw()
        raw["thermal"]["L_degas"] = -1.68e5
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.thermal.L_degas == -1.68e5
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno >= logging.WARNING)
        assert "thermal.L_degas" in text

    @pytest.mark.parametrize("L", [0.0, 1.68e5], ids=["zero", "positive"])
    def test_nonnegative_L_no_warning(self, tmp_path, caplog, L):
        """L ≥ 0 — без предупреждения; L = 0 (теплота дегазации выключена) — граница."""
        raw = _minimal_raw()
        raw["thermal"]["L_degas"] = L
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    # L, μ_JT,o, μ_JT,g: знак по физике любой (P8 §5), проверяется только
    # конечность (DEBT-049). Замер до DEBT-049 (vault/issues/debt-049/probes/
    # red_state.out.txt, раздел 1): все 9 случаев при p_wf = 10 и 6 МПа
    # проходили load_config и from_config, а run падал в solve_banded scipy —
    # «array must not contain infs or NaNs», без имени параметра.
    # _write_json пишет NaN и ±inf литералами JSON NaN, Infinity, -Infinity.
    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")],
                             ids=["nan", "inf", "-inf"])
    @pytest.mark.parametrize("key", ["L_degas", "mu_JT_oil", "mu_JT_gas"])
    def test_nonfinite_scalar_rejected(self, tmp_path, key, value):
        """NaN и ±inf в L, μ_JT,o, μ_JT,g → ValueError с полным именем параметра."""
        raw = _minimal_raw()
        raw["thermal"][key] = value
        with pytest.raises(ValueError, match=f"thermal.{key} .*конечным"):
            load_config(_write_json(tmp_path, raw))

    # Конечность проверяется раньше знака. При обратном порядке в журнал
    # ушло бы предупреждение о знаке (L < 0 или μ_JT,o > 0), а следом
    # отказ — два сообщения о разных причинах.
    @pytest.mark.parametrize("key, value", [
        ("L_degas", float("-inf")),
        ("mu_JT_oil", float("inf")),
    ], ids=["L_minus_inf", "mu_JT_oil_plus_inf"])
    def test_nonfinite_no_sign_warning(self, tmp_path, caplog, key, value):
        """Не конечное значение со «знаком предупреждения»: отказ без предупреждения."""
        raw = _minimal_raw()
        raw["thermal"][key] = value
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            with pytest.raises(ValueError, match=f"thermal.{key}"):
                load_config(_write_json(tmp_path, raw))
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_positive_mu_JT_oil_warns(self, tmp_path, caplog):
        """μ_JT,o > 0 — предупреждение, не отказ (решение пользователя, DEBT-049)."""
        # μ_JT = v(αT − 1)/c_p: у нефти αT ≈ 0.3, μ_JT,o ≈ −4e-7 К/Па.
        # +4e-7 — знак ε = −μ_JT из литературы (Шарафутдинов и др., 2019);
        # так было в конфигах примеров до 2026-09-29.
        raw = _minimal_raw()
        raw["thermal"]["mu_JT_oil"] = 4.0e-7
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.thermal.mu_JT_oil == 4.0e-7
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno >= logging.WARNING)
        assert "thermal.mu_JT_oil" in text

    def test_negative_mu_JT_gas_no_warning(self, tmp_path, caplog):
        """μ_JT,g < 0 при μ_JT,o < 0 — без отказа и без предупреждения."""
        # У газа μ_JT < 0 законен выше давления инверсии: проверка конечности
        # не должна стать проверкой знака, а предупреждение — касаться газа.
        # μ_JT,o = −4e-7 — значение конфигов проекта (нагрев нефти).
        raw = _minimal_raw()
        raw["thermal"].update(mu_JT_oil=-4.0e-7, mu_JT_gas=-4.0e-6)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert (cfg.thermal.mu_JT_oil, cfg.thermal.mu_JT_gas) == (-4.0e-7, -4.0e-6)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# Поля float секций — по аннотациям dataclass, как в _check_numeric_fields:
# новое поле попадает в тест без правки списка. grid — без float-полей
# (N — int), интервалы истории — отдельными тестами (номер объекта JSON).
_FLOAT_FIELDS = [
    (section, f.name)
    for section, cls in (("geometry", GeometryConfig), ("rock", RockConfig),
                         ("pvt", PVTConfig), ("relperm", RelPermConfig),
                         ("thermal", ThermalConfig), ("initial_conditions", InitialConfig),
                         ("time", TimeConfig), ("numerics", NumericsConfig))
    for f in fields(cls) if f.type == "float"
]


# Число и конечность любого числового поля (DEBT-051). Замер до DEBT-051
# (vault/issues/debt-051/probes/red_state.out.txt, 24 ч при p_wf = 6 МПа):
# NaN в p0, porosity и ещё 11 полях — отказ после дробления первого шага до
# dt/512 с советом увеличить max_retries; skin = ±inf, p_wf = +inf — расчёт
# без добычи; min_bhp = NaN — ограничение по забою снято молча (забой
# 7.12 МПа при min_bhp = 15 МПа); строка или null — TypeError без имени поля.
class TestValidationNumbers:
    """Числовые поля конфига: число (не строка, null, bool) и конечное (DEBT-051)."""

    def test_field_list_covers_known_fields(self):
        """Список float-полей из аннотаций содержит известные поля, их не меньше 31."""
        # Страж способа отбора: если аннотации сменят вид («float | None»),
        # список опустеет вместе с проверкой в _check_numeric_fields
        known = {("geometry", "r_well"), ("rock", "porosity"), ("pvt", "rho_o_std"),
                 ("relperm", "n_o"), ("thermal", "L_degas"), ("initial_conditions", "p0"),
                 ("time", "dt_integration"), ("numerics", "skin")}
        assert known <= set(_FLOAT_FIELDS)
        # 37 до DEBT-008: удалены p_ref, start_day, dt_min, dt_max, newton_rtol, newton_atol
        assert len(_FLOAT_FIELDS) >= 31

    @pytest.mark.parametrize("value", [float("nan"), float("inf")], ids=["nan", "inf"])
    @pytest.mark.parametrize("section, key", _FLOAT_FIELDS,
                             ids=[f"{s}.{k}" for s, k in _FLOAT_FIELDS])
    def test_nonfinite_rejected(self, tmp_path, section, key, value):
        """NaN и inf в float-поле секции → ValueError «<секция>.<поле> должно быть конечным»."""
        raw = _minimal_raw()
        raw.setdefault(section, {})[key] = value
        with pytest.raises(ValueError, match=rf"{section}\.{key} должно быть конечным"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("section, key, value", [
        ("rock", "porosity", "0.2"),           # строка-число: был TypeError без имени
        ("time", "dt_integration", "3600"),
        ("initial_conditions", "p0", "abc"),
        ("geometry", "h", None),               # null в обязательном числе
        ("rock", "permeability", True),        # было 1 м² — отказ после dt/512
        ("numerics", "skin", False),
        ("thermal", "c_p_oil", "2000"),
    ], ids=["porosity_str", "dt_integration_str", "p0_text", "h_null",
            "permeability_true", "skin_false", "c_p_oil_str"])
    def test_non_number_rejected(self, tmp_path, section, key, value):
        """Строка, null, true/false в float-поле → ValueError «… должно быть числом»."""
        raw = _minimal_raw()
        raw.setdefault(section, {})[key] = value
        with pytest.raises(ValueError, match=rf"{section}\.{key} должно быть числом"):
            load_config(_write_json(tmp_path, raw))

    def test_nonfinite_in_int_field_rejected(self, tmp_path):
        """NaN в целом поле (grid.N) — тоже отказ по конечности."""
        # `N < 1` NaN пропускает: сравнение с NaN ложно
        raw = _minimal_raw()
        raw["grid"]["N"] = float("nan")
        with pytest.raises(ValueError, match=r"grid\.N должно быть конечным"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("value", [float("nan"), float("inf")], ids=["nan", "inf"])
    @pytest.mark.parametrize("interval, key", [
        ({"control": "pressure", "p_wf": 6e6}, "dt"),
        ({"control": "pressure", "p_wf": 6e6}, "p_wf"),
        ({"control": "rate", "q_oil": 5.787e-4, "min_bhp": 6e6}, "q_oil"),
        ({"control": "rate", "q_oil": 5.787e-4, "min_bhp": 6e6}, "min_bhp"),
    ], ids=["dt", "p_wf", "q_oil", "min_bhp"])
    def test_interval_nonfinite_rejected(self, tmp_path, interval, key, value):
        """NaN и inf в поле интервала истории → ValueError с history[i].<поле>."""
        # Второй интервал испорчен — номер в сообщении указывает на него
        raw = _minimal_raw()
        good = {"dt": 3600.0, **interval}
        raw["time"]["history"] = [good, dict(good, **{key: value})]
        with pytest.raises(ValueError, match=rf"history\[1\]\.{key} должно быть конечным"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("key, value", [("p_wf", "6e6"), ("dt", True)],
                             ids=["p_wf_str", "dt_true"])
    def test_interval_non_number_rejected(self, tmp_path, key, value):
        """Строка или bool в поле интервала → ValueError «history[i].<поле> должно быть числом»."""
        raw = _minimal_raw()
        good = {"dt": 3600.0, "control": "pressure", "p_wf": 6e6}
        raw["time"]["history"] = [good, dict(good, **{key: value})]
        with pytest.raises(ValueError, match=rf"history\[1\]\.{key} должно быть числом"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("key, value", [
        ("duration", float("nan")), ("dt_out", float("nan")),
        ("duration", float("inf")), ("dt_out", "3600"),
    ], ids=["duration_nan", "dt_out_nan", "duration_inf", "dt_out_str"])
    def test_block_fields_checked(self, tmp_path, key, value):
        """duration, dt_out краткой формы — число и конечное до round(duration / dt_out)."""
        # До DEBT-051 NaN давал «cannot convert float NaN to integer» без имени поля
        raw = _minimal_raw()
        block = {"duration": 86400.0, "dt_out": 3600.0, "control": "pressure", "p_wf": 6e6}
        block[key] = value
        raw["time"]["history"] = [block]
        with pytest.raises(ValueError, match=rf"history\[0\]\.{key} должно быть"):
            load_config(_write_json(tmp_path, raw))

    def test_integer_values_accepted(self, tmp_path):
        """Целые числа JSON в float-полях допустимы (dt_integration: 3600 в baseline.json)."""
        raw = _minimal_raw()
        raw["geometry"]["h"] = 10
        cfg = load_config(_write_json(tmp_path, raw))
        assert (cfg.geometry.h, cfg.time.dt_integration) == (10, 3600)


# Скважина: скин и забойное давление против p0 (DEBT-056). Замер до DEBT-056
# (vault/issues/debt-056/probes/skin_range.out.txt, baseline, 24 ч при
# p_wf = 6 МПа): s = −0.5 и −2 — отказ после дробления шага до dt/512 с советом
# увеличить max_retries (проводимость забойной грани прототипа
# 2πkh/(ln(r_1/r_w) + s) < 0, ln(r_1/r_w) = 0.031); s = 1e6, p_wf = 25 МПа,
# min_bhp = 25 МПа при p0 = 20 МПа — расчёт без притока и без сообщения.
def _warning_messages(caplog):
    """Тексты записей журнала уровня WARNING и выше."""
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def _history_raw(second):
    """Минимальный конфиг с двумя объектами истории: добыча при 10 МПа и second."""
    raw = _minimal_raw()
    raw["time"]["history"] = [
        {"dt": 86400, "control": "pressure", "p_wf": 10e6}, second]
    return raw


# Признаки двух предупреждений о скине — фрагменты, которых нет в другом
# сообщении: доля притока при s > 50 (DEBT-056) и скин вне уравнения
# энергии при s > 0 (BUG-029)
_INFLOW = "от притока без скина"
_ENERGY = "В уравнении энергии его нет"


class TestValidationWell:
    """Скин ≥ 0; предупреждения при skin > 0 (BUG-029), > 50 и p_wf, min_bhp ≥ p0 (DEBT-056)."""

    # −0.01 — внутри окна T_w > 0 (у _minimal_raw ln(r_1/r_w) = ln 500 / 20 = 0.31),
    # но отрицательный скин в проекте не предусмотрен (решение пользователя)
    @pytest.mark.parametrize("skin", [-0.01, -0.5, -2.0],
                             ids=["small", "acid", "fracture"])
    def test_negative_skin_rejected(self, tmp_path, skin):
        """Любой s < 0 → ValueError с именем поля."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with pytest.raises(ValueError, match=r"numerics\.skin = .* < 0"):
            load_config(_write_json(tmp_path, raw))

    def test_negative_skin_message_gives_equivalent_radius(self, tmp_path):
        """Обход в сообщении: r_well = r_w·e^(−s) = 0.1·e^0.5 = 0.1649 м, оговорка о температуре."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": -0.5}
        with pytest.raises(ValueError) as exc:
            load_config(_write_json(tmp_path, raw))
        text = str(exc.value)
        assert "geometry.r_well" in text and "0.1649" in text
        assert "температура забоя" in text

    # −1e300 — конечное (проходит DEBT-051), но r_w·e^(−s) переполнил бы np.exp:
    # сравнение с R_ext — в логарифмах, RuntimeWarning превращён здесь в ошибку
    @pytest.mark.filterwarnings("error::RuntimeWarning")
    @pytest.mark.parametrize("skin", [-7.0, -1e300], ids=["minus7", "minus1e300"])
    def test_equivalent_radius_beyond_drainage(self, tmp_path, skin):
        """s = −7: r_w·e^7 = 109.7 м ≥ R_ext = 50 м — обход неприменим, сообщение так и говорит."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with pytest.raises(ValueError, match="неприменим"):
            load_config(_write_json(tmp_path, raw))

    def test_zero_skin_silent(self, tmp_path, caplog):
        """s = 0 (все конфиги проекта) — без отказа и без предупреждений."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": 0.0}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == 0.0
        assert _warning_messages(caplog) == []

    # Скин входит только в гидродинамику (проводимость забойной грани); в
    # уравнении энергии забойная грань при добыче вклада не даёт (eq:QJT_disc,
    # eq:mdot_disc). Решение пользователя (BUG-029): предупреждать при любом
    # s > 0. О доле притока — строго при s > 50 (DEBT-056): здесь его нет
    @pytest.mark.parametrize("skin", [0.01, 5.0, 50.0],
                             ids=["small", "damaged", "threshold"])
    def test_positive_skin_warns_energy(self, tmp_path, caplog, skin):
        """0 < s ≤ 50 — одно предупреждение: скин не входит в уравнение энергии."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1
        assert _ENERGY in msgs[0]
        assert "numerics.skin" in msgs[0] and "T_wf" in msgs[0]

    # Установившийся однофазный приток: p_e − p_wf = qμ/(2πkh)·(ln(R_ext/r_w) + s),
    # из них qμ/(2πkh)·s — на скин-зоне; эта часть перепада в T не входит.
    # У _minimal_raw R_ext/r_w = 50/0.1 = 500, ln 500 = 6.2146
    def test_skin_energy_warning_gives_drawdown_share(self, tmp_path, caplog):
        """s = 2: доля депрессии на скин-зоне 2 / (ln 500 + 2) = 24.3 %."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": 2.0}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        energy = [m for m in _warning_messages(caplog) if _ENERGY in m]
        assert len(energy) == 1 and "24.3%" in energy[0]

    @pytest.mark.parametrize("skin", [50.5, 1e3, 1e6], ids=["above", "1e3", "1e6"])
    def test_large_skin_warns(self, tmp_path, caplog, skin):
        """s > 50 — два предупреждения: о доле притока (DEBT-056) и о температуре (BUG-029)."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        msgs = _warning_messages(caplog)
        # По одному каждого вида, оба называют поле
        assert len(msgs) == 2
        assert sum(_INFLOW in m for m in msgs) == 1
        assert sum(_ENERGY in m for m in msgs) == 1
        assert all("numerics.skin" in m for m in msgs)

    def test_large_skin_warning_gives_inflow_ratio(self, tmp_path, caplog):
        """s = 1000, R_ext/r_w = 500: доля притока ln 500 / (ln 500 + 1000) = 0.6 %."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": 1000.0}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        # Сообщение о притоке — по признаку, не по порядку: при s > 0 есть и второе
        inflow = [m for m in _warning_messages(caplog) if _INFLOW in m]
        assert len(inflow) == 1 and "0.6%" in inflow[0]

    @pytest.mark.parametrize("p_wf", [20e6, 25e6], ids=["equal_p0", "above_p0"])
    def test_pwf_not_below_p0_warns(self, tmp_path, caplog, p_wf):
        """p_wf ≥ p0 = 20 МПа во втором объекте истории — одно предупреждение с history[1]."""
        # При добыче p ≤ p0 во всём пласте: интервал целиком без притока (eq:bc_pwf_shutin)
        raw = _history_raw({"dt": 86400, "control": "pressure", "p_wf": p_wf})
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1
        assert "history[1]" in msgs[0] and "p_wf" in msgs[0]

    def test_min_bhp_not_below_p0_warns(self, tmp_path, caplog):
        """control='rate', q_oil > 0, min_bhp = 25 МПа > p0 — одно предупреждение с history[1]."""
        raw = _history_raw({"dt": 86400, "control": "rate",
                            "q_oil": 5.787e-4, "min_bhp": 25e6})
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1
        assert "history[1]" in msgs[0] and "min_bhp" in msgs[0]

    # q_oil = 0 — намеренный останов (примеры 16, 17: min_bhp = 101325 Па);
    # min_bhp при нулевом дебите на итог не влияет — предупреждать не о чем
    @pytest.mark.parametrize("min_bhp", [101325.0, 25e6], ids=["atm", "above_p0"])
    def test_shut_in_by_rate_silent(self, tmp_path, caplog, min_bhp):
        """control='rate', q_oil = 0 — без предупреждения при любом min_bhp."""
        raw = _history_raw({"dt": 86400, "control": "rate",
                            "q_oil": 0.0, "min_bhp": min_bhp})
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        assert _warning_messages(caplog) == []

    def test_block_warns_once(self, tmp_path, caplog):
        """Блок {duration, dt_out} с p_wf > p0: 24 интервала, предупреждение — одно."""
        # Одно на объект JSON: номер объекта — место правки (как у ошибок, FEAT-018)
        raw = _minimal_raw()
        raw["time"]["history"] = [{"duration": 86400, "dt_out": 3600,
                                   "control": "pressure", "p_wf": 25e6}]
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert len(cfg.time.history) == 24
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1 and "history[0]" in msgs[0]

    def test_production_silent(self, tmp_path, caplog):
        """Штатный конфиг: s = 0, p_wf = 10 МПа < p0 — предупреждений нет."""
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, _minimal_raw()))
        assert _warning_messages(caplog) == []

    # Предупреждения — после всех отказов: конфиг с ошибкой в другом поле не
    # выдаёт сначала предупреждение, а следом отказ (два сообщения о разном)
    @pytest.mark.parametrize("change, error", [
        ({"history_p_wf": 25e6, "porosity": 0.0}, "porosity"),
        ({"skin": 1e3, "max_retries": 25}, "max_retries"),
    ], ids=["pwf_and_porosity", "skin_and_max_retries"])
    def test_no_warning_before_error(self, tmp_path, caplog, change, error):
        """Ошибка в другом поле → ValueError без предупреждений о скине и забое."""
        raw = _minimal_raw()
        if "history_p_wf" in change:
            raw["time"]["history"][0]["p_wf"] = change["history_p_wf"]
            raw["rock"]["porosity"] = change["porosity"]
        else:
            raw["numerics"] = {"skin": change["skin"],
                               "max_retries": change["max_retries"]}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            with pytest.raises(ValueError, match=error):
                load_config(_write_json(tmp_path, raw))
        assert _warning_messages(caplog) == []


# ═════════════════════════════════════════════════════════════
# D2. Мёртвые поля (DEBT-008): удалены, проверены или переданы решателю
# ═════════════════════════════════════════════════════════════

# Удалённые из схемы ключи (секция, ключ). Решатель их не читал: абсурдные
# значения 12 полей проходили _validate и фабрику, прототип считал со своими
# умолчаниями (vault/issues/debt-008/probes/red_state.out.txt). Поэтому старый
# конфиг загружается — ключ пропускается с предупреждением, результат тот же.
_REMOVED = [("rock", "p_ref"), ("time", "start_day"),
            ("numerics", "dt_min"), ("numerics", "dt_max"),
            ("numerics", "newton_rtol"), ("numerics", "newton_atol"),
            ("output", "format")]

_SECTION_CLASSES = {"rock": RockConfig, "time": TimeConfig,
                    "numerics": NumericsConfig, "output": OutputConfig}


class TestRemovedKeys:
    """Удалённые из схемы ключи: предупреждение и пропуск (DEBT-008)."""

    @pytest.mark.parametrize("section, key", _REMOVED,
                             ids=[f"{s}.{k}" for s, k in _REMOVED])
    def test_warns_and_loads(self, tmp_path, caplog, section, key):
        """Старый конфиг с удалённым ключом загружается; в журнале — имя ключа и DEBT-008."""
        raw = _minimal_raw()
        raw.setdefault(section, {})[key] = "npz" if key == "format" else 1.0
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        # Поля в объекте нет: значение не могло никуда попасть
        assert not hasattr(getattr(cfg, section), key)
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno >= logging.WARNING)
        assert f"{section}.{key}" in text and "DEBT-008" in text

    def test_removed_keys_are_not_fields(self):
        """Удалённый ключ не совпадает с живым полем: пропуск не прячет настоящий параметр."""
        for section, key in _REMOVED:
            names = {f.name for f in fields(_SECTION_CLASSES[section])}
            assert key not in names, f"{section}.{key} — поле dataclass"

    def test_unknown_key_still_rejected(self, tmp_path):
        """Опечатка вне списка удалённых — по-прежнему отказ, а не молчаливый пропуск."""
        raw = _minimal_raw()
        raw["numerics"] = {"newton_max_itr": 15}
        with pytest.raises(TypeError, match="newton_max_itr"):
            load_config(_write_json(tmp_path, raw))

    def test_no_warning_before_error(self, tmp_path, caplog):
        """Удалённый ключ и ошибка в другом поле → ValueError без предупреждений.

        Порядок DEBT-056 (load_config): предупреждения — только после всех
        проверок _validate, конфиг с ошибкой их не выдаёт. Ловит журнал
        удалённых ключей в _drop_removed_keys, до разбора секций.
        """
        raw = _minimal_raw()
        raw["time"]["start_day"] = 0.0
        raw["rock"]["porosity"] = 1.5
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            with pytest.raises(ValueError, match="porosity"):
                load_config(_write_json(tmp_path, raw))
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_project_configs_have_no_removed_keys(self):
        """В configs/ и tests/data/ удалённых ключей нет — загрузка без предупреждений.

        Конфиги примеров — test_examples.py::TestConfigs::test_no_removed_keys.
        Без этой чистки test_in_range_no_warnings (configs/table_pvt) и
        test_no_range_warnings (configs/baseline.json) ловили бы предупреждение.
        """
        root = Path(__file__).parent.parent
        paths = (sorted((root / "configs").rglob("*.json"))
                 + sorted((root / "tests" / "data").glob("*/config.json")))
        assert len(paths) >= 8
        for path in paths:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for section, key in _REMOVED:
                assert key not in raw.get(section, {}), \
                    f"{path.relative_to(root)}: {section}.{key}"


class TestLiteralValidation:
    """Строковые литералы grid.type и output.log_level (DEBT-008)."""

    @pytest.mark.parametrize("value", ["cartesian", 1], ids=["cartesian", "int"])
    def test_grid_type_rejected(self, tmp_path, value):
        """Сетки, которой нет, — отказ; до DEBT-008 расчёт молча шёл на логарифмической."""
        raw = _minimal_raw()
        raw["grid"]["type"] = value
        with pytest.raises(ValueError, match=r"grid\.type"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("value", ["DEBG", "", 5], ids=["typo", "empty", "int"])
    def test_log_level_rejected(self, tmp_path, value):
        """Опечатка в уровне журнала — отказ; до DEBT-008 setup_logging молча ставил INFO."""
        raw = _minimal_raw()
        raw["output"] = {"log_level": value}
        with pytest.raises(ValueError, match=r"output\.log_level"):
            load_config(_write_json(tmp_path, raw))

    def test_log_level_case_insensitive(self, tmp_path):
        """«debug» допустим: setup_logging приводит имя к верхнему регистру (log.py)."""
        raw = _minimal_raw()
        raw["output"] = {"log_level": "debug"}
        assert load_config(_write_json(tmp_path, raw)).output.log_level == "debug"


class TestOutputFields:
    """Состав штатного вывода: output.title, n_profiles, steady_state, closed_form_overlays (FEAT-030).

    Поля читает run_case (report/pipeline.py) и команда расчёта. Опечатка в
    конфиге заказчика не должна молча менять состав вывода — как log_level
    до DEBT-008: значение вне допустимых отвергает load_config с именем поля.
    """

    def test_output_defaults(self, tmp_path):
        """Без полей: заголовок — по папке конфига, 4 опорных момента, стационар выключен, наложения p и S_g.

        steady_state = false по умолчанию — решение пользователя 2026-10-13:
        замкнутое решение и асимптотика T — пределы t -> inf, в сценарии
        заказчика стационар может быть не достигнут.
        """
        cfg = load_config(_write_json(tmp_path, _minimal_raw()))
        assert cfg.output.title is None
        assert cfg.output.n_profiles is None
        assert cfg.output.steady_state is False
        assert cfg.output.closed_form_overlays == ["p", "Sg"]

    def test_output_fields_read(self, tmp_path):
        """Заданные значения читаются как есть."""
        raw = _minimal_raw()
        raw["output"] = {"title": "Скв. 1", "n_profiles": 5, "steady_state": True,
                         "closed_form_overlays": ["p"]}
        out = load_config(_write_json(tmp_path, raw)).output
        assert (out.title, out.n_profiles, out.steady_state,
                out.closed_form_overlays) == ("Скв. 1", 5, True, ["p"])

    @pytest.mark.parametrize("field_name, value", [
        ("title", ""),                          # пустой заголовок — опечатка
        ("title", 5),
        ("n_profiles", 1),                      # один момент эволюции не показывает
        ("n_profiles", 2.5),
        ("n_profiles", True),                   # bool — подкласс int
        ("n_profiles", "6"),
        ("steady_state", 1),                    # 1 вместо true
        ("steady_state", "true"),
        ("steady_state", None),
        ("closed_form_overlays", "p"),          # строка вместо списка
        ("closed_form_overlays", ["T"]),        # наложения T замкнутого решения нет
        ("closed_form_overlays", ["p", "p"]),
    ], ids=["title_empty", "title_int", "n_profiles_1", "n_profiles_float",
            "n_profiles_true", "n_profiles_str", "steady_int", "steady_str",
            "steady_null", "overlays_str", "overlays_T", "overlays_repeat"])
    def test_output_field_rejected(self, tmp_path, field_name, value):
        """Недопустимое значение → ValueError с именем поля output.<поле>."""
        raw = _minimal_raw()
        raw["output"] = {field_name: value}
        with pytest.raises(ValueError, match=rf"output\.{field_name}"):
            load_config(_write_json(tmp_path, raw))


class TestNumericsWiredFields:
    """Поля Ньютона, которые фабрика и адаптер передают прототипу (DEBT-008)."""

    @pytest.mark.parametrize("key", ["newton_max_iter", "max_active_set_iter"])
    @pytest.mark.parametrize("value", [0, 2.5, True], ids=["zero", "fraction", "bool"])
    def test_int_field_rejected(self, tmp_path, key, value):
        """Лимит итераций — целое ≥ 1: при 0 Ньютон не делает ни одной итерации, bool — опечатка."""
        raw = _minimal_raw()
        raw["numerics"] = {key: value}
        with pytest.raises(ValueError, match=rf"numerics\.{key} должен быть целым"):
            load_config(_write_json(tmp_path, raw))

    @pytest.mark.parametrize("key", ["rs_switch_tol", "sg_switch_tol"])
    @pytest.mark.parametrize("value", [0.0, -1e-5], ids=["zero", "negative"])
    def test_switch_tol_rejected(self, tmp_path, key, value):
        """Допуск переключения фаз > 0: при −1e-5 газ включался бы в недонасыщенной нефти."""
        raw = _minimal_raw()
        raw["numerics"] = {key: value}
        with pytest.raises(ValueError, match=rf"numerics\.{key} должен быть > 0"):
            load_config(_write_json(tmp_path, raw))

    def test_defaults_match_prototype(self):
        """Умолчания конфига = умолчаниям прототипа и адаптера: без numerics счёт прежний."""
        # Фабрика и адаптер передают эти поля всегда; разойдись умолчания —
        # сменились бы истории всех примеров. Сверка с сигнатурами, а не с
        # числами: смена умолчания в прототипе тоже ловится.
        import inspect
        from radial_blackoil.blackoil import RadialBlackOilModel
        from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
        init = inspect.signature(RadialBlackOilModel.__init__).parameters
        adv = inspect.signature(RadialBlackOilModel.advance).parameters
        ada = inspect.signature(PrototypeHydroAdapter.__init__).parameters
        nc = NumericsConfig()
        assert nc.rs_switch_tol == init["rs_switch_tol"].default
        assert nc.sg_switch_tol == init["sg_switch_tol"].default
        assert nc.newton_max_iter == adv["max_newton"].default == ada["max_newton"].default
        assert (nc.max_active_set_iter == adv["max_active_iter"].default
                == ada["max_active_iter"].default)


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
        """Краткая форма baseline.json даёт тот же список, что 96 явных объектов.

        baseline — сутки при 15 МПа и трое суток при 10 МПа с записью раз
        в час. До DEBT-014 конфиг хранил 96 явных объектов, с DEBT-014 —
        два блока {duration, dt_out}. Явная форма строится здесь: перевод
        не изменил ни число интервалов, ни их длины, ни управление.
        """
        raw = json.loads(BASELINE.read_text(encoding="utf-8"))
        # Конфиг — краткой формой; иначе сравнение ниже сверяло бы явную
        # форму саму с собой
        assert len(raw["time"]["history"]) == 2
        raw["time"]["history"] = (
            [{"dt": 3600.0, "control": "pressure", "p_wf": 15e6}] * 24
            + [{"dt": 3600.0, "control": "pressure", "p_wf": 10e6}] * 72)
        explicit = load_config(_write_json(tmp_path, raw)).time.history
        assert load_config(BASELINE).time.history == explicit

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
