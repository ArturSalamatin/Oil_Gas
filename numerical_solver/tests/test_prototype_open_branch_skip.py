"""DEBT-040: запасной путь advance при BHP не пробует заведомо несогласованную ветку «открыта».

Запасной путь (BUG-014, RadialBlackOilModel._fallback) при управлении забойным
давлением перебирает ветки скважины: «закрыта» (поток через забой нулевой,
согласована при p0 <= p_wf) и «открыта» (отбор q = WI*lambda*(p0 - p_wf) >= 0,
согласована при p0 >= p_wf). Если давление на контуре p_ext и давления
старого состояния во всех ячейках не выше p_wf, то при отборе ни одна ячейка
не поднимется выше p_wf (принцип максимума уравнения давления): p0 <= p_wf,
ветка «открыта» несогласована. Останов «p_wf = p_ext» после добычи — ровно этот
случай: сквозной расчёт конфига 20 пробовал её 1488 раз, принял 0, на неё ушло
38 % времени останова. Теперь в этом случае она не пробуется; принятые шаги не
меняются.

План: vault/plans/debt-040 shutin-skip-failing-stages.md; числа —
vault/issues/debt-040/probes/plan_tests_check.out.txt.
"""

import numpy as np
import pytest

# Логика ступеней без Ньютона (подмена _advance_phases) и реальный шаг останова
# сценария rs300 — помощники и фикстура тестов BUG-020
from .test_prototype_phase_switching import (  # noqa: F401
    DT_STAGE4, OPEN, OPEN3, OPEN4, ORIG, SHUT, SHUT3, SHUT4,
    _assert_restored, _install_fake_phases, shutin_start)
# Модель Nabor_1b (p_ext = 200 бар) и состояние после часа отбора при 100 бар
from .test_prototype_well_branch import _model, drawn_down  # noqa: F401

P_EXT_NABOR = 200.0   # давление на контуре модели Nabor_1b, бар
P_WF_ABOVE = 210.0    # p_wf выше p_ext и всех давлений drawn_down (max 200.0 бар)
ALL_BHP_KEYS = (ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4)


# ═══════════════════════════════════════════════════════════
# A. Перебор веток на подмене _advance_phases
# ═══════════════════════════════════════════════════════════

class TestOpenBranchSkipLogic:
    """Какие (ступень, ветка) перебирает advance; старт с «закрыта» (p0 старое = 111.7 бар)."""

    def test_skipped_when_hopeless(self, drawn_down):
        # p_wf = 210 > p_ext = 200 >= max p_old: «открыта» несогласована на всех
        # ступенях. Ступени 1-3 отказывают, ступень 4 на «закрыта» сходится с
        # p0 = 205 <= 210. До DEBT-040: [ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4].
        model = _model(P_WF_ABOVE)
        model.phase_switching_stage = True
        assert model.p_outer_bar == P_EXT_NABOR
        assert drawn_down.pressure_bar.max() <= P_WF_ABOVE
        plan = {k: (False, 0.0, 3) for k in ALL_BHP_KEYS}
        plan[SHUT4] = (True, 205.0, 20)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3, SHUT4]
        assert rep.converged and rep.phase_switching
        assert (rep.well_branch, rep.well_switches) == ("shut", 0)
        _assert_restored(model)

    def test_all_fail_when_hopeless(self, drawn_down):
        # Отказ всех ступеней: ни одной попытки «открыта». Поля Ньютона отчёта —
        # исходного алгоритма (DEBT-030: 15 итераций, невязка 15.0 у подмены),
        # поля ветки — последней попытки: «закрыта», 0 смен (до DEBT-040 —
        # «открыта», 1 смена). Эти поля не пишутся ни в один выходной файл.
        model = _model(P_WF_ABOVE)
        model.phase_switching_stage = True
        plan = {k: (False, 0.0, 9) for k in ALL_BHP_KEYS}
        plan[ORIG] = (False, 0.0, 15)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3, SHUT4]
        assert not rep.converged
        assert rep.iterations == 15 and rep.residual_inf == 15.0
        assert (rep.well_branch, rep.well_switches) == ("shut", 0)
        _assert_restored(model)

    def test_skipped_at_target_equal_outer(self, drawn_down):
        # Останов «p_wf = p_ext»: условие нестрогое (p_ext <= p_wf, max p_old <= p_wf).
        # Состояние обрезано до 200 бар: у drawn_down max p = 200.000000 на границе.
        model = _model(P_EXT_NABOR)
        model.phase_switching_stage = True
        old = drawn_down.copy()
        old.pressure_bar = np.minimum(old.pressure_bar, P_EXT_NABOR)
        plan = {k: (False, 0.0, 3) for k in ALL_BHP_KEYS}
        plan[SHUT4] = (True, 199.0, 20)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(old, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3, SHUT4]
        assert rep.converged and rep.well_branch == "shut"
        _assert_restored(model)

    def test_prototype_default_skips_too(self, drawn_down):
        # Правка без флага (решение пользователя 2026-10-07): прототип по умолчанию
        # (три ступени) тоже не пробует «открыта». «Закрыта» здесь сходится, но
        # несогласована (p0 = 215 > 210 — на настоящем Ньютоне при этих давлениях
        # невозможно, это подмена): ступень отказывает без попытки «открыта».
        model = _model(P_WF_ABOVE)
        assert model.phase_switching_stage is False
        plan = {k: (False, 0.0, 3) for k in ALL_BHP_KEYS}
        plan[ORIG] = (False, 0.0, 15)
        plan[SHUT] = plan[SHUT3] = (True, 215.0, 4)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3]
        assert not rep.converged
        _assert_restored(model)

    def test_tried_when_outer_above_target(self, drawn_down):
        # p_ext = 200 > p_wf = 195: приток с контура может поднять p0 выше p_wf —
        # ветка «открыта» возможна и пробуется на каждой ступени, как до DEBT-040
        model = _model(195.0)
        model.phase_switching_stage = True
        calls = _install_fake_phases(model, {k: (False, 0.0, 3) for k in ALL_BHP_KEYS})
        model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4]
        _assert_restored(model)

    def test_tried_when_old_pressure_above_target(self, drawn_down):
        # p_ext = 200 <= p_wf = 210, но в старом состоянии ячейка 6 при 215 бар
        # (например, после закачки): приток из неё может поднять p0 выше p_wf.
        # Условия на p0 старого состояния мало — нужен максимум по ячейкам.
        model = _model(P_WF_ABOVE)
        model.phase_switching_stage = True
        old = drawn_down.copy()
        old.pressure_bar[6] = 215.0
        assert old.pressure_bar[0] <= P_WF_ABOVE   # старт — с «закрыта»
        calls = _install_fake_phases(model, {k: (False, 0.0, 3) for k in ALL_BHP_KEYS})
        model.advance(old, 3600.0)
        assert calls == [ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4]
        _assert_restored(model)


# ═══════════════════════════════════════════════════════════
# B. Реальный шаг останова «p_wf = p_ext» (сценарий rs300)
# ═══════════════════════════════════════════════════════════

def test_bhp_shutin_step_without_open_branch(shutin_start):
    """Шаг 168.75 с при p_wf = p_ext: ветка «открыта» не пробуется, итог прежний.

    Замер плана (plan_tests_check.out.txt): до DEBT-040 ветки решений по
    ступеням 1-4 — [-, shut, open, shut, open, shut] (обе «open» не сходятся
    за 10 итераций), после — без «open»; итог побитово тот же: p(r_w) =
    174.434873 бар, двухфазных 250, ветка «закрыта», ступень 4.
    """
    model, ps, p_ext = shutin_start
    model.set_bhp_control(p_ext)
    branches = []
    base = model._advance_phases

    def spy(state_old, dt_s, max_active_iter=12, max_newton=15):
        branches.append(model._well_branch)
        return base(state_old, dt_s, max_active_iter, max_newton)

    model._advance_phases = spy
    try:
        new, rep = model.advance(ps, DT_STAGE4)
    finally:
        del model._advance_phases   # вернуть метод класса: фикстура общая для модуля
    assert branches == [None, "shut", "shut", "shut"]
    assert rep.converged and rep.phase_switching and rep.well_branch == "shut"
    assert new.pressure_bar[0] == pytest.approx(174.434873, abs=1e-5)
    assert int(new.gas_active.sum()) == 250
    _assert_restored(model)
