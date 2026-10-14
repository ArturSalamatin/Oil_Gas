"""BUG-028: цикл набора фаз прототипа не считает в лимит проходы, которые только снимают газ.

Первый шаг добычи из равновесия в примерах 19 и 21 (c_o = c_r = 0) короче 120 с / 5 с не
сходился: первый, однофазный проход стационарен и включает газ в 342 из 350 ячеек, дальше
газ снимается только с внешнего края набора, 1-24 ячейки за проход, а лимит
max_active_iter = 12 проходов кончался раньше (при 1 с нужно 62 прохода, при 0.01 с — 182).
Теперь лимит — на проходы с включением газа; всего проходов не больше max_active_iter + N.

План: vault/plans/bug-028 first-step-phase-set.md; замеры — vault/issues/bug-028/probes/.
"""

import copy
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.units import BAR_TO_PA
from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.state import BlackOilState

from .test_prototype_cell_tolerance import _build

EXAMPLES = Path(__file__).parent.parent / "examples"
DT_NABOR = 3600.0        # шаг подменных проходов на Nabor_1b; подменный Ньютон его не читает


def _first_step(name):
    """Модель фабрики примера и начальное состояние прототипа; управление — первого интервала, как ставит адаптер."""
    cfg = load_config(EXAMPLES / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    # prototype_adapter.solve, шаг 1: забойное давление в бар до advance
    model.set_bhp_control(cfg.time.history[0].p_wf / BAR_TO_PA)
    ps = BlackOilState(pressure_bar=init.p / BAR_TO_PA, rs_sm3_sm3=init.Rs.copy(),
                       sg=init.Sg.copy(), gas_active=(init.regime == 1))
    return model, ps


@pytest.fixture(scope="module")
def ex19():
    """Пример 19: R_s0 = 150, p0 = 247 бар, p_b = 241.85 бар, p_wf = 30 бар, c_o = c_r = 0, N = 350."""
    return _first_step("19_rs150_cooling")


@pytest.fixture(scope="module")
def ex21():
    """Пример 21: R_s0 = 100, p0 = 177 бар, p_b = 172.23 бар, p_wf = 30 бар, c_o = c_r = 0, N = 350."""
    return _first_step("21_rs100_cooling")


# ═══════════════════════════════════════════════════════════
# A. Первый шаг добычи из равновесия сходится ступенью 1
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("example, dt, passes, cells, p_well", [
    ("ex19", 0.01, 182, 30, 78.13),
    ("ex19", 1.0, 62, 98, 38.38),
    ("ex19", 5.27, 41, 129, 34.84),
    ("ex21", 1.0, 78, 82, 36.28),
])
def test_first_production_step_converges(request, example, dt, passes, cells, p_well):
    """Шаг dt из равновесия при глубокой депрессии ниже p_b решает ступень 1 advance.

    Проход 1 включает газ в 342 (21 — 339) ячейках из 350; дальше газ снимается по краю
    набора, без новых включений, и проходов нужно больше 12 (числа — passes400.out.txt,
    first_step_v1.out.txt). До BUG-028 все четыре ступени отказывали (лимит 12 проходов
    ступеней 1-3, 40 итераций ступени 4). Ловит: возврат лимита на проходы снятия; подъём
    max_active_iter вместо исправления дал бы тот же итог здесь, но не в C1, C3.
    """
    model, ps = request.getfixturevalue(example)
    # Умолчания advance (12 проходов, 15 итераций) — те же, что передаёт адаптер из конфига
    new, rep = model.advance(ps, dt)
    assert rep.converged and not rep.fallback          # решила ступень 1, без запасных
    assert rep.active_set_iterations == passes          # больше 12: проходы снятия не в счёт
    assert int(new.gas_active.sum()) == cells           # зона у забоя растёт с dt
    assert new.pressure_bar[0] == pytest.approx(p_well, abs=0.01)
    assert np.all((new.sg >= 0.0) & (new.sg <= 1.0))


# ═══════════════════════════════════════════════════════════
# B. Механизм: проход 1 стационарен при c_o = c_r = 0
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("dt", [0.01, 86400.0])
def test_first_pass_steady_switches_gas_on_almost_everywhere(ex19, dt):
    """Проход 1 (все ячейки однофазные) включает газ в 342 из 350 ячеек при любом dt.

    Недонасыщенная нефть несжимаема (c_o = c_r = 0): проход 1 даёт стационарный профиль
    давления, и при запасе (p0 - p_b)/(p0 - p_wf) = 0.024 он ниже p_b почти везде — при
    0.01 с и при сутках одинаково (stages.out.txt). При max_active_iter = 1 проход 1 с
    включением исчерпывает лимит, как и до BUG-028. Ловит: смену входа примера 19
    (c_o > 0 — тогда тесты A не про BUG-028).
    """
    model, ps = ex19
    _, rep = model._advance_phases(ps, dt, max_active_iter=1)
    assert rep.exit_reason == "active_set"
    assert rep.active_set_iterations == 1
    assert rep.phase_switches == 342


# ═══════════════════════════════════════════════════════════
# C. Счёт проходов: подменный Ньютон на Nabor_1b, N = 12
# ═══════════════════════════════════════════════════════════

def _scripted(model, script):
    """Подменить _newton_fixed_active_set: каждый вызов — следующий проход из script.

    ("on", idx) — включить газ в ячейках idx; ("off_edge",) — снять газ с наибольшей по
    индексу двухфазной ячейки (при пустом наборе — без переключений); ("none",) — без
    переключений. Раскладка z — как pack (blackoil.py): [p, x], x = S_g у двухфазных,
    R_s у однофазных. Включение — R_s > R_s,sat + rs_switch_tol (1e-5), снятие —
    S_g < -sg_switch_tol (1e-9): прочим ячейкам S_g = 0.1 и R_s = R_s,sat - 1.
    """
    steps = iter(script)

    def fake(z0, state_old, dt_s, gas_active, max_iter=15):
        step = next(steps)
        p = state_old.pressure_bar
        rs_sat = model.pvt.rs_sat(p)
        x = np.where(gas_active, 0.1, rs_sat - 1.0)
        if step[0] == "on":
            idx = np.asarray(list(step[1]))
            x[idx] = rs_sat[idx] + 1.0
        elif step[0] == "off_edge":
            active = np.flatnonzero(gas_active)
            if active.size:
                x[active.max()] = -1e-3
        return np.concatenate([p, x]), BlackOilNewtonReport(True, 1, 0.0)

    model._newton_fixed_active_set = fake


@pytest.fixture
def nabor():
    """Модель Nabor_1b на 12 ячейках, состояние без газа (200 бар); подмена Ньютона снимается после теста."""
    model, state = _build(12)
    yield model, state
    if "_newton_fixed_active_set" in vars(model):
        del model._newton_fixed_active_set


def test_switch_off_passes_not_counted(nabor):
    """Включение 6 ячеек, пять проходов снятия по краю, затем без переключений — сходится при лимите 2.

    Проход 1 с включением расходует 1 из 2; проходы 2-6 только снимают газ и лимит не
    тратят; проход 7 без переключений — сходимость. До BUG-028 — отказ 'active_set' после
    2 проходов. Ловит: счёт проходов снятия.
    """
    model, s = nabor
    _scripted(model, [("on", range(6))] + [("off_edge",)] * 5 + [("none",)])
    new, rep = model._advance_phases(s, DT_NABOR, max_active_iter=2)
    assert rep.converged
    assert rep.active_set_iterations == 7
    assert rep.phase_switches == 6 + 5
    assert list(np.flatnonzero(new.gas_active)) == [0]   # сняты 5, 4, 3, 2, 1


def test_switch_on_passes_limited(nabor):
    """Каждый проход включает новую ячейку — отказ 'active_set' после max_active_iter = 3 проходов, как прежде.

    Ловит: снятие лимита с проходов включения — цикл «включение ↔ снятие» шёл бы до
    общего предела max_active_iter + N.
    """
    model, s = nabor
    _scripted(model, [("on", [k]) for k in range(12)])
    _, rep = model._advance_phases(s, DT_NABOR, max_active_iter=3)
    assert not rep.converged and rep.exit_reason == "active_set"
    assert rep.active_set_iterations == 3
    assert rep.phase_switches == 3


def test_total_passes_capped_at_limit_plus_n(nabor):
    """Включение 12, снятие по одной 12 проходов, снова включение 12 и снятие без конца — стоп на 3 + 12 = 15 проходах.

    Включений два (counted = 2 < max_active_iter = 3), выход — по общему пределу
    max_active_iter + N. Переключений 12 + 12 + 12 + 1 = 37. Без предела цикл снимал бы
    газ ещё 11 проходов и «сходился» на пустом наборе. Ловит: потерю общего предела —
    худший случай без него (max_active_iter + 1)(N + 1) проходов.
    """
    model, s = nabor

    def script():
        yield ("on", range(12))
        for _ in range(12):
            yield ("off_edge",)
        yield ("on", range(12))
        while True:
            yield ("off_edge",)

    _scripted(model, script())
    _, rep = model._advance_phases(s, DT_NABOR, max_active_iter=3)
    assert not rep.converged and rep.exit_reason == "active_set"
    assert rep.active_set_iterations == 3 + 12
    assert rep.phase_switches == 37


# ═══════════════════════════════════════════════════════════
# D. Путь пользователя: Simulator + адаптер
# ═══════════════════════════════════════════════════════════

def test_simulator_first_step_one_second():
    """Пример 19, один интервал 1 с, dt_integration = 1 с: расчёт проходит.

    max_retries = 0 — без дробления: при штатных 9 до BUG-028 шаг тоже отказывал, но за
    8 с дробления (split_19_1s.out.txt). Лимиты Ньютона — из конфига через адаптер.
    До BUG-028 — RuntimeError «набор фаз не установился». Ловит: расхождение пути
    адаптера с прямым вызовом advance.
    """
    cfg = load_config(EXAMPLES / "19_rs150_cooling" / "config.json")
    first = copy.deepcopy(cfg.time.history[0])
    first.dt = 1.0
    cfg.time.history = [first]
    cfg.time.dt_integration = 1.0
    cfg.numerics.max_retries = 0
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    st = sim.run(init).states[-1]
    assert st.p[0] / BAR_TO_PA == pytest.approx(38.38, abs=0.01)
    assert int(np.count_nonzero(st.regime == 1)) == 98
