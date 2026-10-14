"""DEBT-054: отчёт Ньютона прототипа называет причину отказа, текст отказа — какое условие не выполнено.

После BUG-022 решение Ньютона принимается, только если выполнены абсолютный критерий
||F||_inf <= atol + rtol*max(||F_0||_inf, 1e-9) (с BUG-025 atol не ниже предела округления
κ·ε·M_max/Δt, Ур. (eq:newton_abs_tol) problem_statement.tex) и условие по ячейке
max_c |F_c,i|*dt/PV_i <= cell_tol. Решение, отвергнутое только условием ячейки, выглядело
в отчёте как «итераций 4, невязка 6.51e-15, не сошлось» (BUG-018 при N = 350, шаг
86400 с): ни допуска, ни меры ячеек, ни причины выхода (линейный поиск встал на пределе
округления). Теперь отчёт несёт residual_tol, cell_measure (на той же невязке, что
residual_inf) и exit_reason; адаптер печатает их и какое условие не выполнено; Simulator
дописывает текст адаптера в свой при исчерпании дробления. Отказ ступени 4 пишет число
выполненных итераций, а не max_iter (DEBT-061, поглощена DEBT-054).

План: vault/plans/debt-054 newton-failure-diagnostics.md; замеры —
vault/issues/debt-054/probes/failure_census.out.txt, test_scenarios.out.txt.

DEBT-055: отчёт отказа несёт ещё cell_floor — предел округления меры ячеек на том же
приближении, меру вектора |J|·ulp(z) (eq:newton_cell_floor); текст отказа его печатает и
говорит, если отказ «только по ячейке» стоит на пределе.
План: vault/plans/debt-055 cell-tol-roundoff-floor.md; замеры —
vault/issues/debt-055/probes/.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.hydro.prototype_adapter import _failure_details
from gpn_multiphase_solver.units import BAR_TO_PA
from radial_blackoil import blackoil
from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.state import BlackOilState

from .test_prototype_activation_cap import _sim
from .test_prototype_cell_tolerance import (  # noqa: F401
    _build as _nabor, _measure, CELL_TOL, DT, DT_STAGE4, shutin)
from .test_prototype_globalization import ORIG3, _install_fake_reports
from .test_prototype_well_branch import _model, drawn_down  # noqa: F401

ATOL, RTOL = 1e-11, 1e-8      # умолчания обоих Ньютонов прототипа (atol_sm3s, rtol)


def _tol(model, z0, s_old, dt, mask):
    """Абсолютный допуск Ньютона по Ур. (eq:newton_abs_tol) — те же операции, что в прототипе."""
    # max(atol, κ·ε·M_max/Δt) + rtol·max(‖F(z0)‖∞, 1e-9); M_max — запасы старого слоя
    # (нефть; газ / s_g). Во всех вызовах ниже предел ниже atol, и max возвращает atol
    f0 = model.residual(z0, s_old, dt, mask)
    oi0, gi0 = model._old_inventories(s_old)
    m = max(float(np.max(np.abs(oi0))), float(np.max(np.abs(gi0))) / model.gas_residual_scale)
    floor = max(ATOL, blackoil.ROUNDOFF_KAPPA * float(np.finfo(float).eps) * m / float(dt))
    return floor + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)


def _bug018_model(N=350):
    """BUG-018 (R_s0 = 500, p_wf = 5 МПа) на N ячейках: модель фабрики, начальное состояние прототипа, шаг 1 сут."""
    sim, init, dt = _sim(N=N)
    model = sim._hydro._model
    # Управление — как ставит адаптер перед advance (prototype_adapter.solve, шаг 1)
    model.set_bhp_control(sim._schedule.intervals[0].bc.well.p_wf / BAR_TO_PA)
    ps = BlackOilState(pressure_bar=init.p / BAR_TO_PA, rs_sm3_sm3=init.Rs.copy(),
                       sg=init.Sg.copy(), gas_active=(init.regime == 1))
    return model, ps, dt


# ═══════════════════════════════════════════════════════════
# A. Ступени 1–3: _newton_fixed_active_set
# ═══════════════════════════════════════════════════════════

class TestFixedActiveSet:
    """Ступени 1–3: _newton_fixed_active_set на Nabor_1b (N = 12, отбор 200 -> 100 бар, 1 ч)."""

    def test_converged_report(self):
        """Сошедшееся решение: допуск, мера той же невязки, выход 'converged'.

        Замер (test_scenarios.out.txt, п. 1): 3 итерации, невязка 9.2e-16, допуск 1.94e-11,
        мера 3.44e-12 — побитово мера теста (pack(unpack(z)) == z).
        Ловит: мера не той невязки или не теми весами, допуск не той формулы.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)
        z0 = model.pack(state)
        z, rep = model._newton_fixed_active_set(z0, state, DT, state.gas_active)
        assert rep.converged and rep.exit_reason == "converged"
        assert rep.residual_tol == _tol(model, z0, state, DT, state.gas_active)
        assert rep.residual_inf <= rep.residual_tol
        assert rep.cell_measure == _measure(model, state, model.unpack(z, state.gas_active), DT)
        assert rep.cell_measure <= CELL_TOL

    def test_cell_test_off(self):
        """Условие по ячейке выключено (cell_tol=None, собственные расчёты прототипа): меры нет, допуск есть."""
        model, state = _nabor(12)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)
        assert rep.converged and rep.exit_reason == "converged"
        assert rep.cell_measure is None and rep.residual_tol is not None

    def test_limit_exit(self):
        """max_iter = 1, а решению нужно 3: выход по лимиту, абсолютное условие не выполнено.

        Замер (п. 2): 1 итерация, невязка 5.7e-5 при допуске 1.9e-11; линейный поиск точку
        принял (z сдвинулся), поэтому выход — лимит, а не линейный поиск.
        Ловит: выход по лимиту записан другой причиной.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active,
                                                max_iter=1)
        assert not rep.converged and rep.iterations == 1 and rep.exit_reason == "max_iter"
        assert rep.residual_inf > rep.residual_tol

    def test_linear_solver_exit(self, monkeypatch):
        """Исключение линейного решателя на первой итерации: выход 'linear_solver', отчёт — о стартовой точке.

        z не сдвинулся: невязка и мера — начального приближения (замер п. 3: невязка = ||F_0||).
        Ловит: мера или невязка не той точки при досрочном выходе.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)

        def broken(*args, **kwargs):
            raise np.linalg.LinAlgError("вырожденная матрица (тест)")

        monkeypatch.setattr(model, "_linear_solve", broken)
        z0 = model.pack(state)
        _, rep = model._newton_fixed_active_set(z0, state, DT, state.gas_active)
        f0 = model.residual(z0, state, DT, state.gas_active)
        assert not rep.converged and rep.iterations == 1 and rep.exit_reason == "linear_solver"
        assert rep.residual_inf == float(np.linalg.norm(f0, np.inf))
        assert rep.cell_measure == _measure(model, state, state, DT)


# ═══════════════════════════════════════════════════════════
# B. Цикл набора фаз: _advance_phases
# ═══════════════════════════════════════════════════════════

def test_active_set_exit():
    """Цикл набора фаз исчерпан (max_active_iter = 1, газ появляется на шаге): выход 'active_set'.

    Невязка — начального приближения нового набора фаз, которое ни один Ньютон не решал:
    допуска нет (None), мера — той же невязки. Замер (п. 4): N = 12 — 5 смен фаз.
    Ловит: отчёт исчерпания набора фаз без причины или с допуском чужого Ньютона.
    """
    model, state = _nabor(12, cell_tol=CELL_TOL)
    _, rep = model._advance_phases(state, DT, max_active_iter=1)
    assert not rep.converged and rep.exit_reason == "active_set"
    assert (rep.active_set_iterations, rep.phase_switches) == (1, 5)
    assert rep.residual_tol is None
    assert rep.cell_measure is not None and rep.cell_measure > 0.0


# ═══════════════════════════════════════════════════════════
# C. Ступень 4: _newton_switching
# ═══════════════════════════════════════════════════════════

class TestSwitching:
    """Ступень 4: _newton_switching на шаге останова 168.75 с (rs300 после 10 сут добычи, q_oil = 0)."""

    def test_converged_report(self, shutin):
        """Замер (п. 5): 16 итераций, невязка 6.9e-15 при допуске 4.38e-11, мера 1.21e-11."""
        model, ps = shutin
        z0 = model.pack(ps, ps.gas_active)
        _, rep = model._newton_switching(ps, DT_STAGE4)
        assert rep.converged and rep.exit_reason == "converged"
        assert rep.residual_tol == _tol(model, z0, ps, DT_STAGE4, ps.gas_active)
        assert rep.residual_inf <= rep.residual_tol and rep.cell_measure <= CELL_TOL
        assert rep.cell_floor is None      # DEBT-055: предел — только у отказа

    def test_limit_only_cell_test(self, shutin):
        """Недостижимый порог 1e-30: 40 итераций, выход по лимиту, абсолютное условие выполнено.

        Тот же класс, что у отказов ступени 4 по памяти на суточном останове
        (failure_census_shutin.out.txt: невязка 7.6e-16, мера 1.29e-8 > 1e-8).
        Замер (п. 5): невязка 8.1e-15 при допуске 4.38e-11. Порог возвращается в finally:
        фикстура модульная.
        """
        model, ps = shutin
        try:
            model.cell_tol = 1e-30
            _, rep = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert not rep.converged and rep.iterations == 40 and rep.exit_reason == "max_iter"
        assert rep.residual_inf <= rep.residual_tol and rep.cell_measure > 1e-30

    def test_linear_solver_break_reports_iterations_run(self, shutin, monkeypatch):
        """DEBT-061: исключение решателя на 3-м вызове — 2 итерации и 'linear_solver', а не 40.

        До правки отчёт после break писал max_iter = 40 (замер п. 6).
        """
        model, ps = shutin
        orig, calls = model._linear_solve, []

        def third_fails(*args, **kwargs):
            calls.append(1)
            if len(calls) == 3:
                raise np.linalg.LinAlgError("вырожденная матрица (тест)")
            return orig(*args, **kwargs)

        monkeypatch.setattr(model, "_linear_solve", third_fails)
        _, rep = model._newton_switching(ps, DT_STAGE4)
        assert not rep.converged
        assert (rep.iterations, rep.exit_reason) == (2, "linear_solver")

    def test_nonfinite_break_reports_iterations_run(self, shutin, monkeypatch):
        """DEBT-061: NaN в направлении 2-го вызова — 1 итерация и 'nonfinite', а не 40 (замер п. 7)."""
        model, ps = shutin
        orig, calls = model._linear_solve, []

        def nan_on_second(*args, **kwargs):
            calls.append(1)
            dz = orig(*args, **kwargs)
            if len(calls) == 2:
                dz = dz.copy()
                dz[0] = np.nan
            return dz

        monkeypatch.setattr(model, "_linear_solve", nan_on_second)
        _, rep = model._newton_switching(ps, DT_STAGE4)
        assert not rep.converged
        assert (rep.iterations, rep.exit_reason) == (1, "nonfinite")


# ═══════════════════════════════════════════════════════════
# D, E. Ветвь скважины и подмена DEBT-030
# ═══════════════════════════════════════════════════════════

class TestBranchAndTotalFailure:
    """_fallback и advance на подменённом _advance_phases (Nabor_1b, p_wf = 150 бар, drawn_down: p[0] = 111.7)."""

    def test_inconsistent_branch_exit(self, drawn_down):
        """Ньютон сошёлся на обеих ветках, обе несогласованы — выход 'branch', а не 'converged'.

        «Закрыта» с p[0] = 160 > p_wf, «открыта» с p[0] = 140 < p_wf (p_ext = 200 > 150 —
        «открыта» пробуется, DEBT-040).
        """
        model = _model(150.0)
        ok = BlackOilNewtonReport(True, 2, 1e-15, residual_tol=1e-11, exit_reason="converged")
        calls = _install_fake_reports(model, {("shut", None, False): (160.0, ok),
                                              ("open", None, False): (140.0, ok)})
        _, rep = model._fallback(drawn_down, 3600.0, 12, 15)
        assert calls == [("shut", None, False), ("open", None, False)]
        assert not rep.converged and rep.exit_reason == "branch"
        assert (rep.well_branch, rep.well_switches) == ("open", 1)

    def test_failed_newton_keeps_its_exit(self, drawn_down):
        """Последняя ветка — отказ Ньютона: выход его ('line_search'), не 'branch'."""
        model = _model(150.0)
        ok = BlackOilNewtonReport(True, 2, 1e-15, residual_tol=1e-11, exit_reason="converged")
        bad = BlackOilNewtonReport(False, 7, 1e-3, residual_tol=1e-11, exit_reason="line_search")
        _install_fake_reports(model, {("shut", None, False): (160.0, ok),
                                      ("open", None, False): (0.0, bad)})
        _, rep = model._fallback(drawn_down, 3600.0, 12, 15)
        assert not rep.converged and rep.exit_reason == "line_search"

    def test_total_failure_carries_original_diagnostics(self, drawn_down):
        """Отказ всех ступеней: допуск, мера и выход — исходного алгоритма, как итерации и невязка (DEBT-030).

        У попыток запасного пути и третьей ступени поля другие: видно, чей отчёт вернул advance.
        Ловит: подмена DEBT-030 без новых полей (допуск и мера последней попытки при невязке ступени 1;
        предел округления последней попытки — DEBT-055).
        """
        model = _model(150.0)
        orig = BlackOilNewtonReport(False, 4, 6.5e-15, 2, 21, residual_tol=5.4e-7,
                                    cell_measure=2.6e-8, exit_reason="line_search",
                                    cell_floor=6.4e-8)
        other = BlackOilNewtonReport(False, 40, 18.2, residual_tol=5.4e-7,
                                     cell_measure=3.6e7, exit_reason="max_iter", cell_floor=2.0e-7)
        branch = BlackOilNewtonReport(True, 0, 0.0, residual_tol=1e-11, cell_measure=0.0,
                                      exit_reason="converged")
        _install_fake_reports(model, {
            ORIG3: (0.0, orig),
            ("shut", None, False): (0.0, other), ("open", None, False): (140.0, branch),
            ("shut", None, True): (0.0, other), ("open", None, True): (140.0, branch)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert not rep.converged
        assert (rep.iterations, rep.residual_inf) == (4, 6.5e-15)
        assert (rep.residual_tol, rep.cell_measure, rep.exit_reason) == (5.4e-7, 2.6e-8, "line_search")
        assert rep.cell_floor == 6.4e-8      # DEBT-055: предел — тоже исходного алгоритма


def test_real_total_failure_only_cell_test():
    """BUG-018 при N = 350, шаг 86400 с: все ступени отказали, отчёт — ступени 1, «только по ячейке».

    Замер (failure_census.out.txt, раздел 1): ступень 1 — линейный поиск после 4 итераций,
    невязка 6.51e-15 при допуске 5.36e-7, мера 2.60e-8 > 1e-8. Ступень 4 отказала иначе
    (лимит 40 итераций, 1101 переключение фаз): в числа отчёта не попадает (DEBT-030),
    видна в попытках (DEBT-069; vault/issues/debt-069/probes/bug018.out.txt).
    Ловит: класс отказа сценария воспроизведения DEBT-054 не виден из отчёта.
    """
    model, ps, dt = _bug018_model()
    assert model.cell_tol == CELL_TOL                  # фабрика включила условие по ячейке
    _, rep = model.advance(ps, dt)
    assert not rep.converged and rep.iterations == 4 and rep.exit_reason == "line_search"
    assert rep.residual_inf <= rep.residual_tol       # абсолютное условие выполнено
    assert rep.cell_measure > CELL_TOL                 # условие по ячейке — нет
    # DEBT-069: все попытки по порядку. Ступени 2 и 3 «открыта» — побитово ступень 1
    # (граница S_g не сработала, ветка не менялась — DEBT-072); «закрыта» на неизменном
    # состоянии сходится за 0 итераций при p[0] = 469 > 50 бар — несогласована
    assert [(a.stage, a.branch) for a in rep.attempts] == [
        (1, ""), (2, "open"), (2, "shut"), (3, "open"), (3, "shut"), (4, "open"), (4, "shut")]
    assert [a.report.exit_reason for a in rep.attempts] == [
        "line_search", "line_search", "branch", "line_search", "branch", "max_iter", "branch"]
    assert [a.report.iterations for a in rep.attempts] == [4, 4, 0, 4, 0, 40, 0]


# ═══════════════════════════════════════════════════════════
# E2. Предел округления меры ячеек (DEBT-055)
# ═══════════════════════════════════════════════════════════

class TestRoundoffFloor:
    """DEBT-055: отчёт отказа несёт cell_floor — меру ячеек вектора |J|·ulp(z) (eq:newton_cell_floor).

    Неизвестные представимы с шагом ulp, и невязку ячейки нельзя сделать меньше доли
    (|J|·ulp(z))_i: Ньютон встаёт на 0.1–0.4 этой меры (замеры плана —
    vault/issues/debt-055/probes/floor_probe.out.txt, failures_floor_*.out.txt). Предел
    растёт как Δt: дробление шага его снимает. Числа тестов — plan_check.out.txt.
    """

    def test_definition_at_linear_solver_exit(self, monkeypatch):
        """Выход 'linear_solver' на первой итерации: якобиан построен в z0 — предел ровно мера |J(z0)|·ulp(z0).

        Ловит: предел по другому приближению, другому якобиану или другим весам.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)

        def broken(*args, **kwargs):
            raise np.linalg.LinAlgError("вырожденная матрица (тест)")

        monkeypatch.setattr(model, "_linear_solve", broken)
        z0 = model.pack(state)
        _, rep = model._newton_fixed_active_set(z0, state, DT, state.gas_active)
        J0, _ = model.finite_difference_jacobian(z0, state, DT, state.gas_active)
        expected = model._cell_measure(abs(J0) @ np.spacing(np.abs(z0)),
                                       model._cell_weights(state, DT))
        assert rep.exit_reason == "linear_solver"
        assert rep.cell_floor == expected

    def test_none_without_failure_or_cell_test(self):
        """Предела нет у сошедшегося решения и при выключенном условии (собственные расчёты прототипа).

        Ловит: лишнее произведение |J|·v на каждом решении; предел без условия по ячейке.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)
        assert rep.converged and rep.cell_floor is None
        # Без cell_tol: max_iter = 1 при трёх нужных итерациях — отказ, но весов нет
        model, state = _nabor(12)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active,
                                                max_iter=1)
        assert not rep.converged and rep.cell_floor is None

    def test_bug018_failure_at_floor(self):
        """BUG-018 при N = 350, шаг 86400 с: ступень 1 встала на пределе — мера 2.60e-8 > 1e-8, предел 6.42e-8.

        Замер (plan_check.out.txt, B): линейный поиск после 4 итераций, мера 2.5962e-8,
        предел 6.4200e-8, отношение 0.40. Ловит: отказ на пределе неотличим от отказа
        недорешённого Ньютона (у того мера много выше предела).
        """
        model, ps, dt = _bug018_model()
        _, rep = model._advance_phases(ps, dt)
        assert not rep.converged and rep.exit_reason == "line_search"
        assert CELL_TOL < rep.cell_measure <= rep.cell_floor
        assert rep.cell_floor == pytest.approx(6.42e-8, rel=1e-3)

    def test_floor_proportional_to_dt(self):
        """Тот же старт при dt/2: предел ровно вдвое меньше — дробление шага его снимает.

        Замер (plan_check.out.txt, B): 3.2100e-8 против 6.4200e-8 — 0.50000. Предел задают
        давления в потоках через грани (eq:newton_cell_floor): вес dt/V_p, производные
        потоков от dt не зависят. При dt/2 мера 1.17e-8 ещё выше порога — Simulator
        отвергает и этот подшаг; dt/4 сходится (история сценария: 86400 и 43200 с —
        отказ, 21600 с — принят; histories_save_base7d8fea7.out.txt).
        Ловит: предел, не зависящий от шага (оценка eps_маш·V_max/V_min до DEBT-055).
        """
        model, ps, dt = _bug018_model()
        _, full = model._advance_phases(ps, dt)
        _, half = model._advance_phases(ps, dt / 2)
        assert not half.converged and half.cell_measure > CELL_TOL
        assert half.cell_floor / full.cell_floor == pytest.approx(0.5, rel=1e-3)

    def test_switching_limit_stops_at_floor(self, shutin):
        """Ступень 4 при недостижимом пороге 1e-30: 40 итераций, мера встала на 0.23 предела.

        Замер (plan_check.out.txt, C): мера 9.77e-12, предел 4.34e-11. Отказы ступени 4
        по памяти на суточном останове — тот же класс: мера 1.29e-8 при пределе 4.65e-8
        (failures_floor_*.out.txt). Порог возвращается в finally: фикстура модульная.
        """
        model, ps = shutin
        try:
            model.cell_tol = 1e-30
            _, rep = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert not rep.converged and rep.exit_reason == "max_iter"
        assert rep.cell_measure <= rep.cell_floor
        assert rep.cell_floor == pytest.approx(4.34e-11, rel=1e-2)


# ═══════════════════════════════════════════════════════════
# F. Текст отказа адаптера
# ═══════════════════════════════════════════════════════════

def test_adapter_message_cell_test_only():
    """Тот же шаг через адаптер: прежний текст и хвост — допуск, мера, предел округления (DEBT-055), выход, невыполненное условие.

    Прежний текст (до DEBT-054) — начало нового: тесты и журналы, искавшие его, совпадают.
    """
    sim, init, dt = _sim(N=350)
    with pytest.raises(HydroConvergenceError) as exc:
        sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
    msg = str(exc.value)
    assert msg.startswith("advance не сошёлся: dt = 8.640e+04 с, t = 0.0000 сут, "
                          "итераций 4, невязка 6.51e-15 (допуск ")
    for part in ("мера ячеек ", "(порог numerics.newton_cell_tol = 1e-08)",
                 "выход: линейный поиск не принял ни одной точки",
                 " — не выполнено только условие по ячейке",
                 # DEBT-055: предел округления ступени 1 и оговорка — мера не выше него
                 ", предел округления 6.42e-08",
                 ", мера не выше предела округления (он пропорционален шагу)"):
        assert part in msg
    assert msg.endswith("; числа — Ньютона ступени 1")


def _rep(res, tol=None, meas=None, reason="", floor=None):
    """Отчёт отказа с полями DEBT-054 (и предела DEBT-055) для проверки текста."""
    return BlackOilNewtonReport(False, 3, res, residual_tol=tol, cell_measure=meas,
                                exit_reason=reason, cell_floor=floor)


_THRESHOLD = " (порог numerics.newton_cell_tol = 1e-08)"


@pytest.mark.parametrize("report, cell_tol, stage, expected", [
    # только ячейка: 1e-15 <= 1e-9, мера 3e-8 > 1e-8 (класс сценария воспроизведения)
    (_rep(1e-15, 1e-9, 3e-8, "line_search"), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", выход: линейный поиск не принял "
     "ни одной точки — не выполнено только условие по ячейке; числа — Ньютона ступени 1"),
    # DEBT-055: только ячейка, мера не выше предела округления — отказ на пределе
    (_rep(1e-15, 1e-9, 3e-8, "line_search", 6e-8), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", предел округления 6.00e-08, "
     "выход: линейный поиск не принял ни одной точки — не выполнено только условие по ячейке, "
     "мера не выше предела округления (он пропорционален шагу); числа — Ньютона ступени 1"),
    # DEBT-055: только ячейка, мера выше предела — Ньютон недорешал, предел только числом
    (_rep(1e-15, 1e-9, 3e-8, "max_iter", 1e-9), 1e-8, 4,
     " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", предел округления 1.00e-09, "
     "выход: исчерпан лимит итераций — не выполнено только условие по ячейке; числа — Ньютона ступени 4"),
    # DEBT-055: оба не выполнены — предел только числом
    (_rep(1e-3, 1e-9, 1.0, "max_iter", 1e-9), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 1.00e+00" + _THRESHOLD + ", предел округления 1.00e-09, "
     "выход: исчерпан лимит итераций — не выполнены оба условия сходимости; числа — Ньютона ступени 1"),
    # только абсолютное
    (_rep(1e-3, 1e-9, 1e-9, "max_iter"), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 1.00e-09" + _THRESHOLD + ", выход: исчерпан лимит итераций"
     " — не выполнено только абсолютное условие; числа — Ньютона ступени 1"),
    # оба не выполнены; ступень 4 по памяти
    (_rep(1e-3, 1e-9, 1.0, "max_iter"), 1e-8, 4,
     " (допуск 1.00e-09), мера ячеек 1.00e+00" + _THRESHOLD + ", выход: исчерпан лимит итераций"
     " — не выполнены оба условия сходимости; числа — Ньютона ступени 4"),
    # оба выполнены: отказ не по сходимости
    (_rep(0.0, 1e-11, 0.0, "branch"), 1e-8, 1,
     " (допуск 1.00e-11), мера ячеек 0.00e+00" + _THRESHOLD + ", выход: ветвь скважины несогласована"
     " — оба условия сходимости выполнены; числа — Ньютона ступени 1"),
    # условие по ячейке выключено: только абсолютное
    (_rep(1e-3, 1e-9, None, "linear_solver"), None, 1,
     " (допуск 1.00e-09), выход: отказ линейного решателя — абсолютное условие не выполнено;"
     " числа — Ньютона ступени 1"),
    # исчерпан набор фаз: допуска нет — вывода об условиях нет
    (_rep(2.7e-4, None, 5e-3, "active_set"), 1e-8, 1,
     ", мера ячеек 5.00e-03" + _THRESHOLD + ", выход: набор фаз не установился; числа — Ньютона ступени 1"),
    # неизвестный код — как есть
    (_rep(1e-3, None, None, "new_code"), None, 1, ", выход: new_code; числа — Ньютона ступени 1"),
    # корень с S_g > 0.98 (ступень 4): условия выполнены, отказ — по границе S_g
    (_rep(1e-15, 1e-11, 1e-12, "sg_bound"), 1e-8, 4,
     " (допуск 1.00e-11), мера ячеек 1.00e-12" + _THRESHOLD + ", выход: корень с S_g > 0.98"
     " — оба условия сходимости выполнены; числа — Ньютона ступени 4"),
    # нечисловое обновление ступени 4
    (_rep(9.2e-3, 4.4e-11, 2.0, "nonfinite"), 1e-8, 4,
     " (допуск 4.40e-11), мера ячеек 2.00e+00" + _THRESHOLD + ", выход: нечисловое приближение"
     " — не выполнены оба условия сходимости; числа — Ньютона ступени 4"),
    # подставной объект тестов без полей DEBT-054 — хвоста нет, текст прежний
    (SimpleNamespace(converged=False, iterations=0, residual_inf=1.0), 1e-8, 1, ""),
    # отчёт, созданный без новых полей (как в старых тестах) — хвоста нет
    (BlackOilNewtonReport(False, 0, 1.0), 1e-8, 1, ""),
])
def test_failure_details(report, cell_tol, stage, expected):
    """Хвост текста отказа по классам: какое условие не выполнено — те же сравнения, что в Ньютоне."""
    assert _failure_details(report, cell_tol, stage) == expected


# ═══════════════════════════════════════════════════════════
# G. Текст отказа Simulator
# ═══════════════════════════════════════════════════════════

def test_simulator_message_ends_with_adapter_text():
    """max_retries = 0: первый же отказ — RuntimeError Simulator; конец текста — текст адаптера.

    До DEBT-054 класс отказа был виден только в цепочке traceback (__cause__).
    """
    sim, init, _ = _sim(N=350, retries=0)
    with pytest.raises(RuntimeError) as exc:
        sim.run(init)
    msg = str(exc.value)
    assert msg.startswith("HydroSolver не сошёлся при дроблении шага до dt/1 = 8.64e+04 с")
    tail = msg.split("Последний отказ гидродинамики: ", 1)[1]
    assert tail == str(exc.value.__cause__)
    assert tail.startswith("advance не сошёлся: dt = 8.640e+04 с")
    assert "не выполнено только условие по ячейке" in tail
    assert "мера не выше предела округления" in tail      # DEBT-055: отказ на пределе
