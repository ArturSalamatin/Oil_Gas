"""BUG-020: четвёртая ступень RadialBlackOilModel.advance — Ньютон с переключением набора фаз на итерациях.

Останов скважины после добычи с развитой газовой зоной (S_g у забоя 0.2-0.45)
не проходил ни одну из трёх ступеней advance:
  М1 — первый шаг: забойная ячейка 0 после закрытия скважины ни для одной
       грани не стоит выше по потоку, коэффициент запаса газа 1/Bg - Rs/Bo при
       51 бар мал (7.4 против 38.9 при 200 бар); Ньютон требует |dSg_0| ~ 0.7 dt[с];
  М2 — следующие шаги: смена ячейки выше по потоку на гранях застойной
       однофазной зоны у забоя; Ньютону не хватает 15 итераций.
Ступень 4 (флаг phase_switching_stage, фабрика GPN включает): запасной путь
BUG-014 с _newton_switching — переключение фаз после каждой итерации с
сохранением отношения газ/нефть, поячеечное ограничение |dp| <= 0.3 p,
|dSg| <= 0.2, без линейного поиска, замораживание ячейки выше по потоку на
гранях после 2 смен направления, доводка без замораживания.

План: vault/plans/bug-020 shutin-phase-switching-newton.md; числа —
vault/issues/bug-020/probes/plan_tests_check.out.txt.
"""

from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from radial_blackoil.state import BlackOilState

DATA = Path(__file__).parent / "data"
# Замороженные сценарии (копии конфигов 20 и 19 на 2026-10-06, история укорочена).
# С примерами НЕ обновляются: регрессии нужен шаг, который решает только ступень 4.
RS300 = DATA / "bug020_rs300" / "config.json"   # 10 сут добычи при 5 МПа
RS150 = DATA / "bug020_rs150" / "config.json"   # 10 сут добычи при 3 МПа + 1 ч q_oil = 0
BAR = 1e5
ATM_BAR = 101325.0 / BAR
DAY = 86400.0
DT_STAGE4 = 168.75    # шаг останова: ступени 1-3 отказывают, ступень 4 сходится (замер)


def _proto(s):
    """SimulationState (Па) -> BlackOilState (бар), как адаптер."""
    return BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(),
                         sg=s.Sg.copy(), gas_active=(s.regime == 1))


@pytest.fixture(scope="module")
def shutin_start():
    """Модель и состояние после 10 сут добычи сценария rs300 (~2 с).

    Замер: p(r_w) = 50.8965 бар, двухфазных 289 из 350, max S_g = 0.4483.
    Модель — из фабрики GPN. Флаг ступени 4 ставится здесь явно: блок A
    проверяет ступень, а не фабрику (её — test_factory_enables_fourth_stage),
    и не зависит от порядка тестов. Тесты, которым нужна модель без ступени,
    выключают флаг и возвращают его в finally.
    """
    cfg = load_config(RS300)
    sim, init = SimulatorFactory.from_config(cfg)
    s = sim.run(init).states[-1]
    model = sim._hydro._model
    model.phase_switching_stage = True
    return model, _proto(s), cfg.initial_conditions.p0 / BAR


def _assert_restored(model):
    """Вне advance атрибуты всех ступеней — по умолчанию."""
    assert model._well_branch is None
    assert model._sg_lower_bound == -0.05
    assert model._line_search_l2 is False
    assert model._sg_step_max is None
    assert model._phase_switching is False
    assert model._upwind_frozen is None and model._upwind_left is None


# ═══════════════════════════════════════════════════════════
# A. Реальный Ньютон: шаг останова, который решает только ступень 4
# ═══════════════════════════════════════════════════════════

class TestFourthStage:
    def test_state_after_production(self, shutin_start):
        """Сценарий не уплыл: состояние перед остановом совпадает с замером плана."""
        _, ps, _ = shutin_start
        assert ps.pressure_bar[0] == pytest.approx(50.8965, abs=1e-3)
        assert int(ps.gas_active.sum()) == 289
        assert ps.sg.max() == pytest.approx(0.4483, abs=1e-4)

    def test_step_needs_fourth_stage(self, shutin_start):
        """Шаг 168.75 с при q_oil = 0: без ступени 4 отказ, с ней — сходится.

        До фикса: ни одна из трёх ступеней не сходится (М1: |dSg_0| = 132 на
        первой итерации). Замер плана: 20 итераций, 127 переключений фаз,
        p(r_w) = 174.4349 бар, двухфазных 250, max S_g = 0.3084.
        """
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        model.phase_switching_stage = False
        try:
            _, rep = model.advance(ps, DT_STAGE4)
            assert not rep.converged
        finally:
            model.phase_switching_stage = True
        new, rep = model.advance(ps, DT_STAGE4)
        assert rep.converged and rep.phase_switching and rep.globalized and rep.fallback
        assert new.pressure_bar[0] == pytest.approx(174.4349, abs=1e-3)
        assert int(new.gas_active.sum()) == 250
        assert new.sg.max() == pytest.approx(0.3084, abs=1e-4)
        _assert_restored(model)

    def test_bhp_shutin_takes_shut_branch(self, shutin_start):
        """Останов как p_wf = p_ext: тот же корень, ветка «закрыта», p(r_w) < p_ext.

        При закрытой ветке поток через забой нулевой, как при q_oil = 0, —
        уравнения совпадают; замер: p(r_w) тот же до бита.
        """
        model, ps, p_ext = shutin_start
        model.set_bhp_control(p_ext)
        new, rep = model.advance(ps, DT_STAGE4)
        assert rep.converged and rep.phase_switching and rep.well_branch == "shut"
        assert new.pressure_bar[0] == pytest.approx(174.4349, abs=1e-3)
        assert new.pressure_bar[0] < p_ext
        _assert_restored(model)

    def test_solution_is_physical_and_conservative(self, shutin_start):
        """Принятое состояние ступени 4: S_g >= 0, R_s <= R_s^sat у однофазных, масса сохранена.

        Баланс компонентов шага (step_global_balance, м³ст) относительно запаса —
        уровень допуска Ньютона; замер 4.7e-16 / 6.6e-16. Ловит: отображение
        переключения, теряющее газ, нефизичный корень расширения S_g < 0.
        """
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        new, rep = model.advance(ps, DT_STAGE4)
        assert rep.converged and rep.phase_switching
        two = new.gas_active
        assert np.all(new.sg[two] >= 0.0) and np.all(new.sg[~two] == 0.0)
        rs_sat = model.pvt.rs_sat(new.pressure_bar)
        assert np.all(new.rs_sm3_sm3[~two] <= rs_sat[~two] + model.rs_switch_tol)
        assert np.all(new.rs_sm3_sm3[two] == rs_sat[two])
        b_oil, b_gas = model.step_global_balance(ps, new, DT_STAGE4)
        oil, gas = model.component_inventories(new)
        assert abs(b_oil) <= 1e-12 * oil.sum()
        assert abs(b_gas) <= 1e-12 * gas.sum()

    def test_solution_solves_original_upwind_scheme(self, shutin_start):
        """Невязка исходной схемы (без замороженных граней) в принятом состоянии — в допуске.

        Замораживание ячейки выше по потоку меняет схему на итерациях; доводка
        возвращает исходную. Ловит: принятие корня «замороженной» схемы.
        Допуск 1e-10 — порядок atol + rtol * ||F0|| Ньютона (1e-11 + 1e-8 * ~3e-3).
        """
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        new, rep = model.advance(ps, DT_STAGE4)
        assert rep.converged and model._upwind_frozen is None
        f = model.residual(model.pack(new), ps, DT_STAGE4, new.gas_active)
        assert np.linalg.norm(f, np.inf) <= 1e-10

    def test_same_root_as_standard_stages(self, shutin_start):
        """Где штатные ступени сходятся (60 с), ступень 4 отдельно находит тот же корень.

        Замер плана: маски фаз равны, max|Δp| = 3.1e-9 бар, |ΔS_g| = 2.4e-11,
        |ΔR_s| = 7.7e-6. Ловит: ступень 4 решает другие уравнения.
        """
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        ref, rep = model.advance(ps, 60.0)
        assert rep.converged and not rep.phase_switching   # решили ступени 1-3
        alt, ra = model._newton_switching(ps, 60.0)
        assert ra.converged
        assert np.array_equal(ref.gas_active, alt.gas_active)
        assert np.max(np.abs(ref.pressure_bar - alt.pressure_bar)) < 1e-6
        assert np.max(np.abs(ref.sg - alt.sg)) < 1e-8
        assert np.max(np.abs(ref.rs_sm3_sm3 - alt.rs_sm3_sm3)) < 1e-3
        _assert_restored(model)

    def test_bitwise_where_standard_stages_converge(self, shutin_start):
        """С флагом и без: шаг добычи 3600 с и шаг останова 60 с — побитово одинаковы.

        Ступень 4 вызывается только после отказа трёх штатных; потоки при
        _upwind_frozen = None считаются по-прежнему.
        """
        model, ps, _ = shutin_start
        pw = 50.0   # бар, добыча при 5 МПа
        out = {}
        for flag in (False, True):
            model.phase_switching_stage = flag
            try:
                model.set_bhp_control(pw)
                a, _ = model.advance(ps, 3600.0)
                model.set_oil_rate_control(0.0, ATM_BAR)
                b, _ = model.advance(ps, 60.0)
            finally:
                model.phase_switching_stage = True
            out[flag] = (a, b)
        for x, y in zip(out[False], out[True]):
            for f in ("pressure_bar", "rs_sm3_sm3", "sg", "gas_active"):
                assert np.array_equal(getattr(x, f), getattr(y, f)), f

    def test_switch_preserves_gas_oil_ratio(self, shutin_start):
        """Переключение фаз ступени 4 сохраняет отношение газ/нефть ячейки (в обе стороны).

        Деактивация (S_g < 0): R_s = (S_o R_s^sat/B_o + S_g/B_g)/(S_o/B_o).
        Активация (R_s > R_s^sat): S_g «закрытого сосуда» — у двухфазного
        состояния то же отношение газ/нефть. Замер: ошибка <= 4e-16.
        """
        model, ps, _ = shutin_start
        pvt, n = model.pvt, model.grid.n
        p = ps.pressure_bar.copy()
        rs_sat = pvt.rs_sat(p)
        bo, bg = pvt.bo(p, rs_sat), pvt.bg(p)

        def ratio(sg):
            return ((1 - sg) * rs_sat / bo + sg / bg) / ((1 - sg) / bo)

        sg_neg = -np.linspace(0.01, 0.5, n)
        x, m, ns = model._switch_phases(p, sg_neg, np.ones(n, bool))
        ok = ratio(sg_neg) > 0          # где отношение < 0, R_s обрезается до 0
        assert ns == n and not m.any()
        assert np.allclose(x[ok], ratio(sg_neg)[ok], rtol=1e-12)

        rs_hi = rs_sat * 1.05 + 1.0
        x, m, ns = model._switch_phases(p, rs_hi, np.zeros(n, bool))
        assert ns == n and m.all()
        free = x < (model.sg_activation_cap or 2.0)   # ограничение BUG-018 не сработало
        assert np.allclose(ratio(x)[free], rs_hi[free], rtol=1e-12)

    def test_attributes_restored_after_exception(self, shutin_start, monkeypatch):
        """Исключение внутри ступени 4 пробрасывается; атрибуты — по умолчанию."""
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)

        def boom(*a, **kw):
            raise RuntimeError("искусственный отказ")

        monkeypatch.setattr(model, "_switch_phases", boom)
        with pytest.raises(RuntimeError):
            model.advance(ps, DT_STAGE4)
        _assert_restored(model)


# ═══════════════════════════════════════════════════════════
# B. Через адаптер: первый час останова сценария rs150
# ═══════════════════════════════════════════════════════════

def _run_rs150(flag):
    """10 сут добычи + час останова; возвращает (история, подшаги первого часа)."""
    cfg = load_config(RS150)
    sim, init = SimulatorFactory.from_config(cfg)
    sim._hydro._model.phase_switching_stage = flag
    subs = []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        r = orig(state, dt, bc)
        if state.t >= 10 * DAY - 1e-6:
            subs.append(r.n_substeps)
        return r

    sim._hydro.solve = solve
    return sim.run(init), subs


class TestShutinFirstHour:
    def test_first_hour_converges(self):
        """Первый час останова после 10 сут добычи (S_g у забоя ~0.44) — одним шагом.

        До фикса: RuntimeError «HydroSolver не сошёлся после 512 подшагов
        (dt_sub=7.03e+00 s)». Замер плана: 1 подшаг; p(r_w) = 176.6086 бар,
        двухфазных 263, max S_g = 0.2281, T(r_w) = 397.7928 К.
        """
        h, subs = _run_rs150(True)
        assert subs[0] == 1
        st = h.states[-1]
        assert st.p[0] / BAR == pytest.approx(176.6086, abs=1e-3)
        assert int(np.count_nonzero(st.regime == 1)) == 263
        assert st.T[0] == pytest.approx(397.7928, abs=1e-3)

    def test_first_hour_fails_without_fourth_stage(self):
        """Без ступени 4 тот же час не проходит и при 512 подшагах (~5 с).

        Фиксирует, что проходит именно ступень 4, а не, например, изменение
        сценария. Начало текста — как цитируют README примеров.
        """
        with pytest.raises(RuntimeError, match="HydroSolver не сошёлся после 512 подшагов"):
            _run_rs150(False)
