"""Таблица полей книги ввода версии 1 (FEAT-033): полнота, единицы, пределы.

Книга ввода переводится в JSON-конфиг (FEAT-035), поэтому таблица полей должна:
  - учитывать каждое поле конфига: строка книги, вычисляемое поле (DERIVED)
    или явное «не из книги» (NOT_FROM_WORKBOOK);
  - задавать единицы с известным переводом в СИ;
  - не быть строже программы (решение 50 плана): значение, которое принимает
    load_config, проверка книги тоже принимает. Исключение — плотности при
    ст. у.: у программы предела нет (DEBT-076), книга требует > 0.
"""

import dataclasses
import json
import re

import numpy as np
import pytest

from gpn_multiphase_solver import factory
from gpn_multiphase_solver.io.config import (
    GeometryConfig, GridConfig, HistoryInterval, InitialConfig, NumericsConfig,
    OutputConfig, PVTConfig, RelPermConfig, RockConfig, ThermalConfig, TimeConfig,
    _validate_interval, load_config)
from gpn_multiphase_solver.io import workbook_format as wf
from gpn_multiphase_solver.units import BAR_TO_PA, MD_TO_M2

SECTIONS = {"geometry": GeometryConfig, "grid": GridConfig, "rock": RockConfig,
            "pvt": PVTConfig, "relperm": RelPermConfig, "thermal": ThermalConfig,
            "initial_conditions": InitialConfig, "time": TimeConfig,
            "numerics": NumericsConfig, "output": OutputConfig}
CONFIG_FIELDS = {f"{s}.{f.name}" for s, cls in SECTIONS.items()
                 for f in dataclasses.fields(cls)}
PARAMS = [p for sheet in wf.PARAM_SHEETS.values() for p in sheet]
COLUMNS = [c for sheet in wf.TABLE_SHEETS.values() for c in sheet]
# Повелительное наклонение в русском тексте книги: «меняйте», «подберите»
IMPERATIVE = re.compile(r"[а-яё]+(?:йте|ите)\b", re.IGNORECASE)


def _demo(key):
    return next(p.demo for p in PARAMS if p.key == key)


# ── Полнота ──────────────────────────────────────────────────

def test_every_config_field_accounted():
    """Каждое поле конфига — ровно в одном месте: строка книги, DERIVED или NOT_FROM_WORKBOOK."""
    keys = {p.key for p in PARAMS}
    for name in sorted(CONFIG_FIELDS):
        where = [name in keys, name in wf.DERIVED, name in wf.NOT_FROM_WORKBOOK]
        assert sum(where) == 1, f"{name}: {where}"


def test_workbook_only_keys():
    """Ключи книги вне конфига — ровно пять; источники DERIVED — ключи книги или SCHEDULE."""
    keys = {p.key for p in PARAMS}
    assert keys - CONFIG_FIELDS == {"format_version", "rock.porosity_ref", "rock.p_ref",
                                    "rock.rho_solid", "rock.c_solid"}
    for target, sources in wf.DERIVED.items():
        assert target in CONFIG_FIELDS
        assert set(sources) <= keys | {"SCHEDULE"}, target


def test_schedule_covers_history_interval():
    """Столбцы SCHEDULE (момент t → длительность dt) — ровно поля HistoryInterval."""
    targets = {c.target for c in wf.SCHEDULE} - {"t"} | {"dt"}
    assert targets == {f.name for f in dataclasses.fields(HistoryInterval)}
    assert {c for c, _ in wf.CONTROL_MODES.values()} == {"pressure", "rate"}
    for _, used in wf.CONTROL_MODES.values():
        assert set(used) <= targets
    assert set(wf.CONTROL_MODES) == set(wf.SCHEDULE[1].choices)


def test_keys_and_labels_unique():
    """Ни ключ, ни подпись не повторяются: строка книги — одно поле."""
    keys = [p.key for p in PARAMS]
    assert len(keys) == len(set(keys))
    for sheet in wf.PARAM_SHEETS.values():
        labels = [p.label for p in sheet]
        assert len(labels) == len(set(labels))


# ── Единицы ──────────────────────────────────────────────────

def test_units_ascii_and_known():
    """Единицы — ASCII (решение 35) и с известным переводом в СИ."""
    for unit in {p.unit for p in PARAMS} | {c.unit for c in COLUMNS}:
        assert unit.isascii(), unit
        assert unit in wf.UNIT_TO_SI, unit


def test_table_headers_carry_unit():
    """Заголовок столбца с единицей оканчивается ней: «Pressure, bar(a)»."""
    for c in COLUMNS:
        if c.unit != "-":
            assert c.header.endswith(", " + c.unit), c.header


@pytest.mark.parametrize("unit, value, si", [
    ("bar(a)", 200.0, 2e7),
    ("1/bar", 4.5e-5, 4.5e-10),
    ("mD", 1.0, MD_TO_M2),
    ("K/MPa", -0.4, -4e-7),
    ("kJ/kg", 230.0, 2.3e5),
    ("h", 1.0, 3600.0),
    ("day", 1.0, 86400.0),
    ("Sm3/day", 86400.0, 1.0),
    ("cP", 2.0, 2e-3),
])
def test_unit_to_si(unit, value, si):
    """Перевод единицы книги в СИ: множитель и направление."""
    assert wf.UNIT_TO_SI[unit](value) == pytest.approx(si, rel=1e-15)


def test_per_unit_conversion_divides():
    """«На единицу» — деление на точный множитель, как c_r в конвертере примера 18."""
    assert wf.UNIT_TO_SI["1/bar"](4.5e-5) == 4.5e-5 / BAR_TO_PA


# ── Пределы ──────────────────────────────────────────────────

@pytest.mark.parametrize("limit, value, ok", [
    (wf.POSITIVE, 0.0, False), (wf.POSITIVE, 1e-300, True),
    (wf.NON_NEGATIVE, -1e-300, False), (wf.NON_NEGATIVE, 0.0, True),
    (wf.POROSITY, 0.0, False), (wf.POROSITY, 1.0, True), (wf.POROSITY, 1 + 1e-15, False),
    (wf.COUNT, 1.0, True), (wf.COUNT, 1.5, False), (wf.COUNT, 0.0, False),
    (wf.Limit(lo=0.0, hi=20.0, integer=True), 20.0, True),
    (wf.Limit(lo=0.0, hi=20.0, integer=True), 21.0, False),
    (wf.ANY, True, False), (wf.ANY, "1", False), (wf.ANY, np.nan, False),
    (wf.ANY, np.inf, False), (wf.ANY, -1e6, True),
])
def test_limit_accepts(limit, value, ok):
    """Граница строгая/нестрогая, целое, bool и строка — не число, nan и inf отвергаются."""
    assert limit.accepts(value) is ok


def test_limit_above_key():
    """R_ext > r_well: равное отвергается, большее — принимается."""
    lim = wf.Limit(above_key="geometry.r_well")
    assert not lim.accepts(0.1, above=0.1)
    assert lim.accepts(0.10000001, above=0.1)


def test_fixed_params_accept_only_their_value():
    """Постоянные строки (решение 65): версия 1, якобиан grouped, решатель СЛАУ sparse."""
    by_key = {p.key: p for p in PARAMS}
    assert {p.key for p in PARAMS if p.fixed} == {
        "format_version", "numerics.jacobian_mode", "numerics.linear_solver"}
    assert by_key["format_version"].accepts(1.0) and not by_key["format_version"].accepts(2.0)
    assert by_key["numerics.jacobian_mode"].accepts("grouped")
    assert not by_key["numerics.jacobian_mode"].accepts("reference")
    assert by_key["numerics.linear_solver"].accepts("sparse")
    assert not by_key["numerics.linear_solver"].accepts("dense")


def test_no_none_in_workbook():
    """Слова «выключено» в книге нет (решение 64): поля с null в JSON требуют число > 0."""
    by_key = {p.key: p for p in PARAMS}
    for key in ("time.dt_after_control_change", "numerics.newton_cell_tol"):
        assert not by_key[key].accepts("none"), key
        assert by_key[key].limit == wf.POSITIVE, key


def test_comments_in_two_languages():
    """Comment — по-английски, «Комментарии» — по-русски, у каждой строки (решение 66).

    Без минуса U+2212 и тире: в формулах — дефис-минус ASCII (замечание 12 пользователя).
    Русский текст описывает, а не велит: «добавляются», не «добавляйте» (замечание
    пользователя 2026-10-17) — повелительное наклонение ловит окончание -йте/-ите.
    """
    for p in PARAMS:
        assert p.comment and p.comment_ru, p.key
        assert not any("а" <= ch.lower() <= "я" for ch in p.comment), p.key
        assert any("а" <= ch.lower() <= "я" for ch in p.comment_ru), p.key
        assert not IMPERATIVE.search(p.comment_ru), (p.key, IMPERATIVE.findall(p.comment_ru))
        for text in (p.comment, p.comment_ru):
            assert not {"−", "–", "—"} & set(text), (p.key, text)


def test_relperm_fixed_rows():
    """Обязательные строки RELPERM (решение 68): S_g = 0 с k_rg = 0, S_g = 1 с k_ro = 0."""
    assert wf.RELPERM_FIRST_ROW == (0.0, None, 0.0)
    assert wf.RELPERM_LAST_ROW == (1.0, 0.0, None)
    for pattern in (wf.RELPERM_FIRST_ROW, wf.RELPERM_LAST_ROW):
        for col, v in zip(wf.RELPERM, pattern):
            assert v is None or col.limit.accepts(v)


def test_demo_values_accepted():
    """Демонстрационное значение каждой строки проходит её предел."""
    for p in PARAMS:
        above = _demo(p.limit.above_key) if p.limit and p.limit.above_key else None
        assert p.accepts(p.demo, above), p.key


# ── Не строже программы (решение 50) ─────────────────────────

def _base_raw():
    """Базовый конфиг в СИ: Стендинг и Кори — load_config не читает CSV."""
    return {
        "geometry": {"r_well": 0.1, "R_ext": 100.0, "h": 10.0},
        "grid": {"N": 100},
        "rock": {"porosity": 0.2, "permeability": 1e-15},
        "pvt": {"model": "standing", "rho_o_std": 800.0, "rho_g_std": 0.727},
        "relperm": {"model": "corey"},
        "thermal": {},
        "initial_conditions": {"p0": 2e7, "T0": 350.0, "Rs0": 50.0},
        "time": {"dt_integration": 3600.0,
                 "history": [{"dt": 86400.0, "control": "pressure", "p_wf": 1.5e7}]},
        "numerics": {},
    }


def _program_accepts(tmp_path, field_path, value_si):
    """load_config принимает базовый конфиг, где поле field_path заменено на value_si."""
    raw = _base_raw()
    section, name = field_path.split(".")
    raw[section][name] = value_si
    path = tmp_path / "c.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    try:
        load_config(path)
    except ValueError:
        return False
    return True


def _probes(p, above):
    """Пробные значения у границ предела строки p, в единицах книги."""
    lim = p.limit
    vals = {p.demo, -1.0, 0.0, 1.0}
    if lim.lo is not None:
        vals |= {lim.lo - 1, lim.lo, lim.lo + 1e-6, lim.lo + 1}
    if lim.hi is not None:
        vals |= {lim.hi - 1e-6, lim.hi, lim.hi + 1e-6, lim.hi + 1}
    if lim.above_key is not None:
        vals |= {above * 0.5, above, above * (1 + 1e-9), above * 2}
    if lim.integer:
        vals = {float(round(v)) for v in vals}
    return sorted(vals)


def _to_si(p, v):
    """Значение ячейки → значение поля JSON, как его запишет перевод."""
    if p.limit.integer:
        return int(v)
    return wf.UNIT_TO_SI[p.unit](v)


def test_excel_not_stricter_than_program(tmp_path):
    """Где программа принимает, а Excel отвергает, — только плотности при ст. у. (DEBT-076)."""
    by_key = {p.key: p for p in PARAMS}
    stricter = set()
    # Прямые поля конфига. Постоянные строки (якобиан, решатель СЛАУ) книга
    # намеренно строже JSON — решение 65; их значения проверяет конструктор прототипа
    for p in PARAMS:
        if p.fixed or p.key not in CONFIG_FIELDS:
            continue
        above = _demo(p.limit.above_key) if p.limit.above_key else None
        for v in _probes(p, above):
            if _program_accepts(tmp_path, p.key, _to_si(p, v)) and not p.accepts(v, above):
                stricter.add(p.key)
    # Производные: φ_ref при p0 = p_ref даёт porosity = φ_ref; ρ_ma, c_ma — произведение
    phi = by_key["rock.porosity_ref"]
    for v in _probes(phi, None):
        if _program_accepts(tmp_path, "rock.porosity", v) and not phi.accepts(v):
            stricter.add(phi.key)
    for key, other in (("rock.rho_solid", "rock.c_solid"), ("rock.c_solid", "rock.rho_solid")):
        p = by_key[key]
        for v in _probes(p, None):
            if (_program_accepts(tmp_path, "rock.rho_cp_solid", v * _demo(other))
                    and not p.accepts(v)):
                stricter.add(key)
    # Плотности: у программы предела нет (DEBT-076), книга требует > 0 (решение 54).
    # Когда DEBT-076 добавит отказ в _validate, множество опустеет — поправить тест
    assert stricter == {"pvt.rho_o_std", "pvt.rho_g_std"}


# ── Таблицы против фабрики ───────────────────────────────────

_FACTORY_TEXT = {wf.POSITIVE: "> 0", wf.NON_NEGATIVE: "≥ 0", wf.FRACTION: "в [0, 1]"}


@pytest.mark.parametrize("sheet, columns, limits", [
    ("OIL_PVT", factory._OIL_PVT_COLUMNS, factory._OIL_PVT_LIMITS),
    ("GAS_PVT", factory._GAS_PVT_COLUMNS, factory._GAS_PVT_LIMITS),
    ("RELPERM", factory._RELPERM_COLUMNS, factory._RELPERM_LIMITS),
])
def test_table_columns_match_factory(sheet, columns, limits):
    """Столбцы таблицы — столбцы CSV фабрики в том же порядке, с теми же пределами."""
    cols = wf.TABLE_SHEETS[sheet]
    assert [c.target for c in cols] == columns
    for c in cols:
        assert limits[c.target][0] == _FACTORY_TEXT[c.limit], c.header


@pytest.mark.parametrize("column, make", [
    ("p_wf", lambda v: HistoryInterval(dt=1.0, control="pressure", p_wf=v * BAR_TO_PA)),
    ("q_oil", lambda v: HistoryInterval(dt=1.0, control="rate", q_oil=v / 86400.0,
                                        min_bhp=1e5)),
    ("min_bhp", lambda v: HistoryInterval(dt=1.0, control="rate", q_oil=0.0,
                                          min_bhp=v * BAR_TO_PA)),
])
def test_schedule_limits_match_validate_interval(column, make):
    """Предел столбца SCHEDULE совпадает с _validate_interval: Excel принимает ⇔ программа."""
    col = next(c for c in wf.SCHEDULE if c.target == column)
    for v in (-1.0, 0.0, 1e-6, 1.0):
        try:
            _validate_interval(make(v), "probe")
            prog = True
        except ValueError:
            prog = False
        assert col.limit.accepts(v) is prog, (column, v)
