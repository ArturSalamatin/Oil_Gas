"""Баланс массы компонентов (DEBT-039): контракты, накопитель, Simulator, укороченные примеры.

Схема гидродинамики консервативна: невязки eq:residual_oil, eq:residual_gas —
изменение запаса в ячейке плюс разность потоков через грани; их сумма по
ячейкам и шагам сворачивается к забою и контуру:
ΔM + ∫G[N] dt − ∫G[0] dt = 0. Накопленная невязка проверяет не физику, а то,
что стоит между невязкой Ньютона и историей: допуск Ньютона, учёт дробления
шага, знаки потоков адаптера.

Конфиги примеров укорочены (6 ч или 2 + 2 ч, N = 25) — тесты идут доли секунды.
"""

import copy
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.mass_balance import (
    MASS_KEYS, MassBalanceAccumulator, compute_mass_balance)
from gpn_multiphase_solver.simulator import Simulator

from ._doubles import LogProfileHydroStub, FailingHydroStub
from .test_simulator import _initial_state, _make_simulator, _single_interval_schedule

# Конфиги примеров; сборка невязки — в пакете (compute_mass_balance, DEBT-011)
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

# Порог относительной невязки (нормировка — сумма модулей членов). Уровень —
# допуск Ньютона прототипа (rtol = 1e-8 к начальной невязке шага, atol =
# 1e-11 м³ст/с на ячейку, условие по ячейке numerics.newton_cell_tol —
# BUG-022), а не округления: замер при планировании DEBT-039 — до 4.5e-10 на
# укороченных конфигах здесь; на полных примерах до 2.9e-8 до BUG-022 и
# 5.6e-9 после (пример 16).
# Дефекты, которые ловит проверка, дают 1e-3...1: поток последнего подшага
# вместо интеграла при дроблении — 9e-2 на шаге.
TOL = 1e-6


def _stub_result(**integrals):
    """HydroResult двойника за шаг 3600 с, с заданными интегралами потоков."""
    _, _, hydro, _, _ = _make_simulator()
    bc = _single_interval_schedule().intervals[0].bc
    return replace(hydro.solve(_initial_state(), 3600.0, bc), **integrals)


def _max_rel(bal):
    """Максимум относительной невязки по записям: нефть и газ вместе."""
    return max(float(np.max(bal["rel_residual_o"])),
               float(np.max(bal["rel_residual_g"])))


# ── Контракты ─────────────────────────────────────────────────

class TestContracts:
    def test_hydro_result_integrals_default_none(self):
        """Без интегралов HydroResult строится как прежде: поля — None.

        Шесть мест в тестах и fluxes.py строят HydroResult без новых полей;
        умолчание None — признак «решатель массу не сохраняет».
        """
        r = _stub_result()
        assert (r.int_G_o_well, r.int_G_o_ext,
                r.int_G_g_well, r.int_G_g_ext) == (None, None, None, None)

    def test_solver_inventories_default_none(self):
        """Метод ABC по умолчанию — None: двойник уравнений не решает."""
        _, _, hydro, _, _ = _make_simulator()
        assert hydro.component_inventories(_initial_state()) is None

    def test_stub_history_without_mass_balance(self):
        """На двойнике без запаса снимки баланса массы — None, расчёт идёт."""
        grid, pvt, hydro, energy, _ = _make_simulator()
        sim = Simulator(grid, hydro, energy, pvt,
                        _single_interval_schedule(dt_hist=7200.0, dt_int=3600.0))
        history = sim.run(_initial_state())
        # Один интервал — две записи: начальная и конец интервала
        assert history.mass_balance == [None, None]


# ── Накопитель ────────────────────────────────────────────────

class TestAccumulator:
    def test_sums_integrals_and_snapshot(self):
        """Интегралы шагов складываются; снимок — запас + суммы, ключи MASS_KEYS."""
        acc = MassBalanceAccumulator()
        r = _stub_result(int_G_o_well=-1.0, int_G_o_ext=-2.0,
                         int_G_g_well=-3.0, int_G_g_ext=-4.0)
        acc.add_step(r)
        acc.add_step(r)
        snap = acc.snapshot((10.0, 20.0))
        assert snap == {"M_o": 10.0, "M_g": 20.0,
                        "cum_o_well": -2.0, "cum_o_ext": -4.0,
                        "cum_g_well": -6.0, "cum_g_ext": -8.0}
        assert tuple(snap) == MASS_KEYS

    def test_missing_integrals_raise_before_accumulation(self):
        """Без любого из int_G_* — RuntimeError, накопитель не тронут.

        Запас без интегралов — несогласованный решатель: баланс по dt·G
        последнего подшага был бы ложным при дроблении шага (DEBT-039).
        """
        acc = MassBalanceAccumulator()
        with pytest.raises(RuntimeError, match="int_G"):
            acc.add_step(_stub_result(int_G_o_well=-1.0))   # три поля — None
        assert acc.snapshot((0.0, 0.0))["cum_o_well"] == 0.0


# ── Simulator ─────────────────────────────────────────────────

class _FluxIntegralStub(LogProfileHydroStub):
    """Двойник с интегралами dt·G и нулевым запасом — проверка учёта шагов в Simulator."""

    def solve(self, state, dt, bc):
        r = super().solve(state, dt, bc)
        # Профиль стационарный, потоки шага постоянны: интеграл = dt·G
        return replace(r, int_G_o_well=dt * r.G_o[0], int_G_o_ext=dt * r.G_o[-1],
                       int_G_g_well=dt * r.G_g[0], int_G_g_ext=dt * r.G_g[-1])

    def component_inventories(self, state):
        return (0.0, 0.0)


class TestSimulatorWiring:
    def test_failed_substep_not_counted(self):
        """Отказавший подшаг в интегралы не попадает (DEBT-015).

        Двойник отказывает на шагах > 1800 с: 3600 ✗ → 1800 ✓ → 1800 ✓.
        Отказавший вызов результата не возвращает — в интеграл он не
        попадает по построению; тест ловит двойной учёт принятых подшагов.
        Потоки двойника постоянны, поэтому интеграл через забой — ровно
        3600·G_o[0]; при двойном учёте было бы 5400·G_o[0] и больше.
        """
        grid, pvt, inner, energy, _ = _make_simulator()
        hydro = FailingHydroStub(_FluxIntegralStub(grid, pvt, inner._relperm),
                                 lambda s, dt: dt > 1800.0)
        sim = Simulator(grid, hydro, energy, pvt,
                        _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
        history = sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0, 1800.0, 1800.0]
        # Не None: FailingHydroStub делегирует запас внутреннему двойнику
        assert history.mass_balance[-1] is not None
        assert history.mass_balance[0]["cum_o_well"] == 0.0
        G0 = history.hydro_results[-1].G_o[0]
        assert history.mass_balance[-1]["cum_o_well"] == pytest.approx(
            3600.0 * G0, rel=1e-12)

    def test_refined_substep_counted_once(self):
        """Локальное дробление второй половины: каждый принятый подшаг учтён ровно один раз.

        Двойник: отказ на шагах > 1800 с и, с t = 1800 с, на шагах > 900 с.
        Подшаги 3600 ✗, 1800 ✓, 1800 ✗, 900 ✓, 900 ✓ — в балансе только три
        принятых (1800 + 900 + 900 с). Интеграл через забой — ровно 3600·G_o[0].
        """
        grid, pvt, inner, energy, _ = _make_simulator()
        hydro = FailingHydroStub(
            _FluxIntegralStub(grid, pvt, inner._relperm),
            lambda s, dt: dt > 1800.0 or (dt > 900.0 and s.t >= 1800.0))
        sim = Simulator(grid, hydro, energy, pvt,
                        _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
        history = sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0, 1800.0, 1800.0, 900.0, 900.0]
        G0 = history.hydro_results[-1].G_o[0]
        assert history.mass_balance[-1]["cum_o_well"] == pytest.approx(
            3600.0 * G0, rel=1e-12)

    def test_inventories_without_integrals_raise(self):
        """Решатель отдаёт запас, но не интегралы — RuntimeError на первом шаге."""

        class _InventoryOnly(LogProfileHydroStub):
            def component_inventories(self, state):
                return (1.0, 1.0)

        grid, pvt, inner, energy, _ = _make_simulator()
        sim = Simulator(grid, _InventoryOnly(grid, pvt, inner._relperm), energy,
                        pvt, _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
        with pytest.raises(RuntimeError, match="int_G"):
            sim.run(_initial_state())


# ── Укороченные конфиги примеров, настоящий решатель ──────────

def _short_config(example: str, n_intervals: int = 1):
    """Конфиг примера: 6 ч одним или n интервалами, N = 25 (как test_energy_balance_examples)."""
    config = load_config(_EXAMPLES / example / "config.json")
    config.grid.N = 25
    iv = copy.deepcopy(config.time.history[0])
    config.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
    for h in config.time.history:
        h.dt = 21600.0 / n_intervals
    config.output.log_level = "WARNING"
    return config


def _run(config):
    simulator, initial_state = SimulatorFactory.from_config(config)
    return simulator.run(initial_state)


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_mass_balance_closes_short(example):
    """Невязка баланса массы — на уровне допуска Ньютона: Стендинг и таблица.

    Источник PVT был разделительной линией в BUG-004 — проверяются обе ветви.
    Замер при планировании: 3.4e-11 (03), 1.0e-12 (04).
    """
    bal = compute_mass_balance(_run(_short_config(example)))
    assert _max_rel(bal) < TOL


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_mass_balance_independent_of_history_structure(example):
    """Снимок баланса массы не зависит от частоты записи — побитово.

    Одни и те же 6 подшагов по 3600 с, одна запись или шесть: интегралы
    складываются в том же порядке, запас — функция побитово равного
    состояния. Восстановление по записям так не умело бы (DEBT-013).
    """
    sparse = _run(_short_config(example, 1))
    dense = _run(_short_config(example, 6))
    assert dense.n_saved == 7
    assert sparse.mass_balance[-1] == dense.mass_balance[-1]


def test_mass_balance_through_shut_in(tmp_path):
    """Баланс массы через останов: 2 ч добычи при 6 МПа, 2 ч останова (q_oil = 0).

    Конфиг примера 16, N = 25, шаг 300 с — как в
    test_energy_balance_examples.py::test_stepped_schedule_matches_uniform_across_shut_in.
    Запись 24 — конец добычи. На останове забой закрыт: интегралы через
    забой не меняются ни в одном бите, а пласт добирает нефть с контура —
    приток за останов равен росту запаса. Замер при планировании: невязка
    1.1e-11 (нефть), 4.5e-10 (газ); приток и рост запаса нефти — по 1.649 м³ст.
    """
    src = _EXAMPLES / "16_well_shut_in" / "config.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw["time"]["history"] = [
        {"dt": 300.0, "repeat": 24, "control": "pressure", "p_wf": 6.0e6},
        {"dt": 300.0, "repeat": 24, "control": "rate", "q_oil": 0.0,
         "min_bhp": 101325.0}]
    raw["time"]["dt_integration"] = 300.0
    path = tmp_path / "shut_in.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    config = load_config(path)
    # Таблицы PVT и ОФП фабрика ищет относительно конфига — каталог примера
    config.config_dir = src.parent
    config.grid.N = 25
    config.output.log_level = "WARNING"

    bal = compute_mass_balance(_run(config))
    assert _max_rel(bal) < TOL
    assert np.all(bal["cum_o_well"][24:] == bal["cum_o_well"][24])
    assert np.all(bal["cum_g_well"][24:] == bal["cum_g_well"][24])
    inflow = bal["inflow_o"][-1] - bal["inflow_o"][24]
    assert inflow > 0.0
    assert bal["dM_o"][-1] - bal["dM_o"][24] == pytest.approx(inflow, rel=1e-6)
