"""DEBT-048: память ступени 4 — шаг после двух шагов, решённых ступенью 4, решается сразу ею.

Останов после добычи с развитой газовой зоной: почти каждый шаг решает только
ступень 4 advance (BUG-020), ступени 1-3 перед ней не сходятся. На непринятые
решения уходило около 80 % итераций Ньютона на останове (замер после BUG-024;
до него — 82-84 %). Прототип отдаёт ступень 4 отдельным методом
advance_fourth_stage — побитово той же, что advance вызывает после отказа трёх
ступеней. Адаптер помнит, сколько принятых подряд шагов решила ступень 4 (при
том же управлении, на продолжении той же траектории), и после STAGE4_MEMORY = 2
таких шагов вызывает её сразу. Её отказ — отказ шага без ступеней 1-3 (Simulator
делит подшаг); после STAGE4_MAX_FAILURES = 2 отказов подряд память
сбрасывается, следующая попытка проходит все ступени.

План: vault/plans/debt-048 shutin-remember-solving-stage.md; числа —
vault/issues/debt-048/probes/plan_tests_check.out.txt.
"""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from gpn_multiphase_solver.bc import RateControl
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.hydro.prototype_adapter import (
    STAGE4_MAX_FAILURES, STAGE4_MEMORY, PrototypeHydroAdapter)
from gpn_multiphase_solver.io.config import load_config

# Логика ступеней без Ньютона (подмена _advance_phases) и реальный шаг останова
# сценария rs300 — помощники и фикстура тестов BUG-020
from .test_prototype_phase_switching import (  # noqa: F401
    ATM_BAR, DT_STAGE4, OPEN4, RS300, SHUT4,
    _assert_restored, _install_fake_phases, shutin_start)
# Модель Nabor_1b (p_ext = 200 бар) и состояние после часа отбора при 100 бар
from .test_prototype_well_branch import _build, _model, drawn_down  # noqa: F401
# Малая модель адаптера (N = 20, BHP 150 бар) и её фикстуры
from .test_prototype_adapter import (  # noqa: F401
    DT, _bc_rate, adapter, bc, initial_state, model, our_grid, our_pvt,
    proto_grid, proto_pvt, proto_rock, proto_rp)

BAR = 1e5


# ═══════════════════════════════════════════════════════════
# A. Ступень 4 отдельно — advance_fourth_stage прототипа
# ═══════════════════════════════════════════════════════════

class TestFourthStageAlone:
    """Модель p_wf = 150 бар, state_old = drawn_down (p[0] = 111.7 < 150): ветки стартуют с «закрыта»."""

    def test_calls_fourth_stage_only(self, drawn_down):
        # Ни исходного алгоритма (ORIG), ни запасного пути без переключения фаз:
        # подмена бросит KeyError на любой ключ, кроме SHUT4. Ступень 4 на «закрыта»
        # сходится с p[0] = 149 <= 150 — согласована. Флаг phase_switching_stage
        # не нужен: он только добавляет ступень в перебор advance.
        model = _model(150.0)
        assert model.phase_switching_stage is False
        calls = _install_fake_phases(model, {SHUT4: (True, 149.0, 20)})
        _, rep = model.advance_fourth_stage(drawn_down, 3600.0)
        assert calls == [SHUT4]
        assert rep.converged and rep.phase_switching and rep.globalized and rep.fallback
        assert (rep.well_branch, rep.iterations) == ("shut", 20)
        _assert_restored(model)

    def test_failure_reports_own_newton(self, drawn_down):
        # Отказ: обе ветки (p_ext = 200 > p_wf = 150 — «открыта» возможна, DEBT-040
        # её не снимает). Отчёт — собственный, последней попытки: исходный алгоритм
        # не запускался, подставлять его поля, как advance (DEBT-030), нечего.
        model = _model(150.0)
        calls = _install_fake_phases(model, {SHUT4: (False, 0.0, 40), OPEN4: (False, 0.0, 40)})
        _, rep = model.advance_fourth_stage(drawn_down, 3600.0)
        assert calls == [SHUT4, OPEN4]
        assert not rep.converged and rep.phase_switching
        assert (rep.iterations, rep.residual_inf) == (40, 40.0)
        _assert_restored(model)

    def test_exception_restores_attributes(self, drawn_down):
        # Исключение внутри ступени пробрасывается; модель не остаётся в режиме ступени 4
        model = _model(150.0)
        _install_fake_phases(model, {SHUT4: "raise"})
        with pytest.raises(RuntimeError):
            model.advance_fourth_stage(drawn_down, 3600.0)
        _assert_restored(model)

    def test_rate_control(self):
        # Управление по дебиту: запасной путь без ветки скважины — одна попытка
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        r4 = (None, None, False, True)
        calls = _install_fake_phases(model, {r4: (True, 190.0, 11)})
        _, rep = model.advance_fourth_stage(state, 60.0)
        assert calls == [r4]
        assert rep.converged and rep.phase_switching
        _assert_restored(model)


def test_fourth_stage_alone_equals_advance(shutin_start):
    """Шаг 168.75 с при q_oil = 0, где ступени 1-3 не сходятся: advance_fourth_stage побитово равен advance.

    На этом равенстве держится память адаптера: шаг, который она отдаёт сразу
    ступени 4, решается так же, как advance решил бы его после трёх отказов.
    Ступень 4 — функция (state_old, dt, управление): всё, что она меняет в модели,
    восстанавливается в finally. Замер аудита 2 (база d7528d4, BUG-024 влит): 16
    итераций, невязка 6.9e-15 в обоих (до BUG-022 — 20 и 4.8e-13). Число итераций
    тест не закрепляет: его сдвигает любая правка критерия сходимости.
    Ловит: ступень, зависящую от предшествующих неудачных попыток.
    """
    model, ps, _ = shutin_start
    model.set_oil_rate_control(0.0, ATM_BAR)
    a, ra = model.advance(ps, DT_STAGE4)
    b, rb = model.advance_fourth_stage(ps, DT_STAGE4)
    assert ra.converged and ra.phase_switching          # решила ступень 4
    for f in ("pressure_bar", "sg", "rs_sm3_sm3", "gas_active"):
        assert np.array_equal(getattr(a, f), getattr(b, f)), f
    assert (rb.converged, rb.iterations, rb.residual_inf) == (True, ra.iterations, ra.residual_inf)
    _assert_restored(model)


# ═══════════════════════════════════════════════════════════
# B. Память адаптера: какие вызовы делает solve (подмена ступеней)
# ═══════════════════════════════════════════════════════════

def _fake_stages(model, monkeypatch, outcomes):
    """Подменить advance и advance_fourth_stage; outcomes — (сошёлся, решила ступень 4) по вызовам.

    Журнал: "все" — advance (ступени 1-4 по порядку), "4" — advance_fourth_stage.
    Состояние возвращается прежним: адаптеру для потоков и забойного давления
    нужно корректное состояние, новое не нужно.
    """
    calls, queue = [], list(outcomes)

    def make(kind):
        def fake(proto_state, dt, *args, **kwargs):
            calls.append(kind)
            converged, stage4 = queue.pop(0)
            return proto_state, SimpleNamespace(
                converged=converged, phase_switching=stage4, iterations=3, residual_inf=1.0)
        return fake

    monkeypatch.setattr(model, "advance", make("все"))
    monkeypatch.setattr(model, "advance_fourth_stage", make("4"))
    return calls


def _solve(adapter, state, bc, ok=True):
    """Один вызов solve. ok=False — ждём отказ и возвращаем то же состояние: повтор, как у Simulator."""
    if ok:
        return adapter.solve(state, DT, bc).state
    with pytest.raises(HydroConvergenceError, match="advance не сошёлся"):
        adapter.solve(state, DT, bc)
    return state


class TestAdapterStage4Memory:
    """Малая модель адаптера (N = 20, BHP 150 бар); исходы ступеней заданы подменой."""

    def test_defaults(self):
        # Вариант m2s замера плана (1.2): M = 2, сброс после 2 отказов подряд
        assert (STAGE4_MEMORY, STAGE4_MAX_FAILURES) == (2, 2)

    def test_two_stage4_steps_arm_memory(self, model, adapter, initial_state, bc, monkeypatch):
        # Два шага подряд решила ступень 4 — третий идёт сразу в неё
        calls = _fake_stages(model, monkeypatch, [(True, True)] * 3)
        s = initial_state
        for _ in range(3):
            s = _solve(adapter, s, bc)
        assert calls == ["все", "все", "4"]

    def test_single_stage4_steps_do_not_arm(self, model, adapter, initial_state, bc, monkeypatch):
        # Шаг, решённый ступенями 1-3, обнуляет серию: одиночные шаги ступени 4
        # (пример 16 — один такой шаг за расчёт) память не включают
        calls = _fake_stages(model, monkeypatch,
                             [(True, True), (True, False), (True, True), (True, True)])
        s = initial_state
        for _ in range(4):
            s = _solve(adapter, s, bc)
        assert calls == ["все"] * 4

    def test_full_stages_failure_keeps_run(self, model, adapter, initial_state, bc, monkeypatch):
        # Отказ полного перебора серию не обнуляет: повтор того же подшага
        # меньшим шагом остаётся на той же траектории (вариант m2s)
        calls = _fake_stages(model, monkeypatch,
                             [(True, True), (False, False), (True, True), (True, True)])
        s = _solve(adapter, initial_state, bc)
        s = _solve(adapter, s, bc, ok=False)
        s = _solve(adapter, s, bc)
        _solve(adapter, s, bc)
        assert calls == ["все", "все", "все", "4"]

    def test_fourth_stage_failure_is_step_failure(self, model, adapter, initial_state, bc, monkeypatch):
        # Отказ ступени 4 по памяти — отказ шага, ступени 1-3 не пробуются (замер:
        # после её отказа они не решили ни одного шага из 2486). Повтор подшага из
        # того же состояния — снова сразу ступень 4: один отказ память не сбрасывает.
        calls = _fake_stages(model, monkeypatch,
                             [(True, True), (True, True), (False, True), (True, True)])
        s = _solve(adapter, initial_state, bc)
        s = _solve(adapter, s, bc)
        s = _solve(adapter, s, bc, ok=False)
        _solve(adapter, s, bc)
        assert calls == ["все", "все", "4", "4"]

    def test_two_failures_reset_memory(self, model, adapter, initial_state, bc, monkeypatch):
        # Два отказа ступени 4 подряд — память сброшена: следующая попытка с того
        # же состояния проходит все ступени (страховка: шаг, который решили бы
        # только ступени 1-3)
        calls = _fake_stages(model, monkeypatch,
                             [(True, True), (True, True), (False, True), (False, True), (True, False)])
        s = _solve(adapter, initial_state, bc)
        s = _solve(adapter, s, bc)
        s = _solve(adapter, s, bc, ok=False)
        s = _solve(adapter, s, bc, ok=False)
        _solve(adapter, s, bc)
        assert calls == ["все", "все", "4", "4", "все"]

    def test_control_change_resets_memory(self, model, adapter, initial_state, bc, monkeypatch):
        # Серия при p_wf = 150 бар; следующий шаг при управлении по дебиту — все ступени
        calls = _fake_stages(model, monkeypatch, [(True, True)] * 3)
        s = _solve(adapter, initial_state, bc)
        s = _solve(adapter, s, bc)
        _solve(adapter, s, _bc_rate(0.0, 1e5))
        assert calls == ["все", "все", "все"]

    def test_other_trajectory_resets_memory(self, model, adapter, initial_state, bc, monkeypatch):
        # Состояние не с конца последнего принятого шага (другое t) — память не
        # действует: она о продолжении той же траектории, а не о модели вообще
        calls = _fake_stages(model, monkeypatch, [(True, True)] * 3)
        s = _solve(adapter, initial_state, bc)
        _solve(adapter, s, bc)
        _solve(adapter, initial_state, bc)
        assert calls == ["все", "все", "все"]

    def test_memory_off(self, model, our_grid, our_pvt, initial_state, bc, monkeypatch):
        # stage4_memory=None — каждый шаг через все ступени, как до DEBT-048
        adapter = PrototypeHydroAdapter(model, our_grid, our_pvt, stage4_memory=None)
        calls = _fake_stages(model, monkeypatch, [(True, True)] * 3)
        s = initial_state
        for _ in range(3):
            s = _solve(adapter, s, bc)
        assert calls == ["все"] * 3


# ═══════════════════════════════════════════════════════════
# C. Реальный останов сценария rs300: память не меняет решение
# ═══════════════════════════════════════════════════════════

N_CHAIN = 6


@pytest.fixture(scope="module")
def shutin_parts():
    """Модель, сетка и PVT адаптера, состояние после 10 сут добычи rs300, ГУ останова (~2 с).

    Замер: p(r_w) = 50.8965 бар, двухфазных 289, max S_g = 0.4483 (как shutin_start).
    Адаптеры тесты создают сами: память — состояние адаптера, общий адаптер
    сделал бы тесты зависимыми от порядка.
    """
    cfg = load_config(RS300)
    sim, init = SimulatorFactory.from_config(cfg)
    s0 = sim.run(init).states[-1]
    h = sim._hydro
    bc_shut = replace(sim._schedule.intervals[-1].bc, well=RateControl(0.0, 101325.0))
    return h._model, h._grid, h._pvt, s0, bc_shut


def test_shutin_chain_bitwise_with_memory(shutin_parts, monkeypatch):
    """Останов q_oil = 0 после 10 сут добычи, 6 шагов по 168.75 с: с памятью и без — побитово (~5 с).

    Без памяти ступень 4 решила шаги 1, 3-6, шаг 2 — ступени 1-3 (замер аудита,
    база d7528d4: итераций 16, 29, 8, 8, 9, 8). С памятью (M = 2) шаги 5 и 6
    идут сразу в ступень 4 и решаются так же, как advance решил бы их после трёх
    отказов. p(r_w) после 6 шагов — 229.967798 бар (и до BUG-022 тоже).
    Ловит: память, которая меняет решение там, где ступени 1-3 не сходятся;
    память, которая не включается на реальном останове.
    """
    model, grid, pvt, s0, bc = shutin_parts
    full_steps, step = [], [0]
    adv = model.advance

    def spy(ps, dt, *a, **kw):
        # шаги, на которых адаптер вызвал advance (все ступени), а не ступень 4 сразу
        full_steps.append(step[0])
        return adv(ps, dt, *a, **kw)

    monkeypatch.setattr(model, "advance", spy)
    runs = {}
    for memory in (None, STAGE4_MEMORY):
        adapter = PrototypeHydroAdapter(model, grid, pvt, stage4_memory=memory)
        full_steps.clear()
        states, s = [], s0
        for k in range(1, N_CHAIN + 1):
            step[0] = k
            s = adapter.solve(s, DT_STAGE4, bc).state
            states.append(s)
        runs[memory] = (states, list(full_steps))
    assert runs[None][1] == [1, 2, 3, 4, 5, 6]
    assert runs[STAGE4_MEMORY][1] == [1, 2, 3, 4]       # шаги 5, 6 — по памяти
    for a, b in zip(runs[None][0], runs[STAGE4_MEMORY][0]):
        for f in ("p", "Sg", "Rs", "regime"):
            assert np.array_equal(getattr(a, f), getattr(b, f)), f
    assert runs[None][0][-1].p[0] / BAR == pytest.approx(229.967798, abs=1e-5)


# ═══════════════════════════════════════════════════════════
# D. Подключение в GPN
# ═══════════════════════════════════════════════════════════

def test_factory_adapter_remembers_stage4():
    """Фабрика GPN создаёт адаптер с памятью ступени 4 (решение пользователя 2026-10-08)."""
    sim, _ = SimulatorFactory.from_config(load_config(RS300))
    assert sim._hydro._stage4_memory == STAGE4_MEMORY
