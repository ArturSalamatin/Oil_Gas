"""DEBT-069: отчёт advance перечисляет попытки ступеней — ступень, ветка, копия отчёта.

При отказе всех ступеней отчёт несёт числа Ньютона ступени 1 (DEBT-030), а поля ветки —
последней попытки. Отчёт ветки «открыта» ступеней 2–4 затирался отчётом «закрыта»
(0 итераций на неизменном состоянии, отвергнута как несогласованная), и причину отказа
этих ступеней в BUG-028 нашла только отдельная проба. Теперь, как только ступень 1 не
решила шаг, отчёт несёт attempts — все попытки по порядку (StageAttempt: ступень, ветка,
копия отчёта); текст отказа адаптера заканчивается строкой попыток.

План: vault/plans/debt-069 stage-attempts-failure-report.md; замеры —
vault/issues/debt-069/probes/ (attempts_probe.py, t04_attempts.py).
"""

from radial_blackoil.blackoil import BlackOilNewtonReport

# Подмена _advance_phases с ключом (ветка, граница S_g, ||F||_2): у каждой ступени свой отчёт
from .test_prototype_globalization import ORIG3, ORIG_REPORT, _install_fake_reports
# Подмена с ключом (ветка, граница, ||F||_2, ступень 4); отчёт (сошлась, its, невязка its)
from .test_prototype_phase_switching import (
    OPEN, OPEN3, OPEN4, ORIG, SHUT, SHUT3, SHUT4, _install_fake_phases)
# Модель Nabor_1b (p_ext = 200 бар) и состояние после часа отбора при 100 бар (p[0] = 111.7)
from .test_prototype_well_branch import _build, _model, drawn_down  # noqa: F401


def _key(a):
    """(ступень, ветка) попытки."""
    return (a.stage, a.branch)


# ═══════════════════════════════════════════════════════════
# A. Сбор попыток в advance и _fallback (подмена _advance_phases)
# ═══════════════════════════════════════════════════════════

class TestAttemptsOnFakeStages:
    """Модель p_wf = 150 бар, drawn_down (p[0] = 111.7 < 150): ветки стартуют с «закрыта»."""

    def test_original_converged_no_attempts(self, drawn_down):
        # Шаг решила ступень 1 (почти все шаги) — попыток нет, отчёт побитово прежний
        model = _model(150.0)
        _install_fake_reports(model, {ORIG3: (151.0, BlackOilNewtonReport(True, 3, 1e-15))})
        _, rep = model.advance(drawn_down, 3600.0)
        assert rep.converged and rep.attempts == ()

    def test_total_failure_lists_every_attempt(self, drawn_down):
        # Отказ трёх ступеней (флаг ступени 4 выключен). Ступени 2 и 3: «закрыта» не сошлась,
        # «открыта» сошлась за 0 итераций, но p[0] = 140 < 150 — несогласована, записана
        # отказом 'branch'. До DEBT-069 отчёт «закрыта» ступеней 2 и 3 терялся.
        model = _model(150.0)
        calls = _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7,
                                                              exit_reason="max_iter")),
            ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0,
                                                                exit_reason="converged")),
            ("shut", None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9,
                                                             exit_reason="line_search")),
            ("open", None, True): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0,
                                                               exit_reason="converged"))})
        _, rep = model.advance(drawn_down, 3600.0)
        # По попытке на каждый вызов _advance_phases, в том же порядке
        assert len(rep.attempts) == len(calls) == 5
        assert [_key(a) for a in rep.attempts] == [
            (1, ""), (2, "shut"), (2, "open"), (3, "shut"), (3, "open")]
        assert [a.report.exit_reason for a in rep.attempts] == [
            "", "max_iter", "branch", "line_search", "branch"]
        assert [a.report.iterations for a in rep.attempts] == [15, 14, 0, 13, 0]
        assert not any(a.report.converged for a in rep.attempts)
        # Подмена DEBT-030 прежняя: поля Ньютона — ступени 1 (ORIG_REPORT: 15, 2.5e-7, 2, 21)
        assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                rep.phase_switches) == (15, 2.5e-7, 2, 21)
        # Копии: своих попыток нет (нет вложенности), с возвращённым отчётом не связаны
        assert all(a.report.attempts == () and a.report is not rep for a in rep.attempts)

    def test_rate_control_one_attempt_per_stage(self):
        # Управление по дебиту: запасной путь без ветки — по попытке на ступень, ветка ''
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            (None, None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            (None, None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9))})
        _, rep = model.advance(state, 60.0)
        assert [_key(a) for a in rep.attempts] == [(1, ""), (2, ""), (3, "")]
        assert [a.report.iterations for a in rep.attempts] == [15, 14, 13]

    def test_accepted_third_stage_carries_attempts(self, drawn_down):
        # Решение пользователя 2026-10-14: попытки — как только ступень 1 не решила шаг,
        # и у принятого шага. Ступень 3 сошлась на «закрыта» (p[0] = 149 <= 150 —
        # согласована): последняя попытка — принятая; поля отчёта — её собственные (17)
        model = _model(150.0)
        _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
            ("shut", None, True): (149.0, BlackOilNewtonReport(True, 17, 2.0e-16, 2, 15))})
        _, rep = model.advance(drawn_down, 3600.0)
        assert rep.converged and rep.iterations == 17
        assert [_key(a) for a in rep.attempts] == [(1, ""), (2, "shut"), (2, "open"), (3, "shut")]
        assert [a.report.converged for a in rep.attempts] == [False, False, False, True]
        assert rep.attempts[2].report.exit_reason == "branch"

    def test_all_four_stages(self, drawn_down):
        # Флаг ступени 4 включён, отказ везде: семь попыток, у ступеней 2–4 — обе ветки
        model = _model(150.0)
        model.phase_switching_stage = True
        plan = {k: (False, 0.0, 9) for k in (SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4)}
        plan[ORIG] = (False, 0.0, 15)
        _install_fake_phases(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert [_key(a) for a in rep.attempts] == [
            (1, ""), (2, "shut"), (2, "open"), (3, "shut"), (3, "open"), (4, "shut"), (4, "open")]
        assert [a.report.iterations for a in rep.attempts] == [15, 9, 9, 9, 9, 9, 9]

    def test_fourth_stage_alone(self, drawn_down):
        # advance_fourth_stage (ступень 4 по памяти адаптера, DEBT-048): только её ветки
        model = _model(150.0)
        _install_fake_phases(model, {SHUT4: (False, 0.0, 40), OPEN4: (False, 0.0, 40)})
        _, rep = model.advance_fourth_stage(drawn_down, 3600.0)
        assert not rep.converged
        assert [_key(a) for a in rep.attempts] == [(4, "shut"), (4, "open")]

    def test_hopeless_open_not_listed(self, drawn_down):
        # p_wf = 210 > p_ext = 200 >= max p_old (drawn_down): «открыта» не пробуется (DEBT-040)
        # и в попытках её нет — видно, что ступени 2–4 пробовали только «закрыта»
        model = _model(210.0)
        model.phase_switching_stage = True
        _install_fake_phases(model, {k: (False, 0.0, 3)
                                     for k in (ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert [_key(a) for a in rep.attempts] == [(1, ""), (2, "shut"), (3, "shut"), (4, "shut")]
