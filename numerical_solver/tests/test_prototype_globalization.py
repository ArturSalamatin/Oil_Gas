"""BUG-016: третья ступень RadialBlackOilModel.advance — глобализованный Ньютон.

Исходный алгоритм advance и запасной путь BUG-014 принимают шаг Ньютона
только при уменьшении ||F||_inf. При массовой активации газовой фазы с
далёким начальным S_g («закрытый сосуд»: 0.55-0.71 при решении 0.22,
пример 14 в версии BUG-016, R_s0 = 150) направление Ньютона не уменьшает ||F||_inf ни при
каком alpha — Ньютон стоит, дробление шага не помогает.

Третья ступень (только при отказе первых двух): запасной путь BUG-014 с
линейным поиском по ||F||_2 (направление Ньютона — направление спуска для
||F||_2^2) и ограничителем |dS_g| <= 0.2 за итерацию (как ds_max в OPM Flow).

План: vault/plans/bug-016 newton-line-search-norm.md.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import NumericsConfig, load_config
from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.state import BlackOilState

# Модель Nabor_1b и состояние после часа отбора — из тестов BUG-014.
# tests/ — пакет (как from ._doubles import ... в test_simulator.py), импорт
# относительный. Импорт фикстуры drawn_down делает её фикстурой и этого модуля.
from .test_prototype_well_branch import _build, _model, drawn_down  # noqa: F401

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SG_STEP_MAX = 0.2   # ограничитель третьей ступени, |dS_g| за итерацию

# Пример 14 в версии коммита BUG-016 (e2fdb43): ветки PVT R_s = 0/150/180,
# p_b(150) = 24 МПа, p0 = 24.5 МПа. Позже пример сменил таблицу PVT (ffc5a46),
# и его первый шаг стал сходиться без третьей ступени. Регрессии BUG-016 нужен
# реальный шаг, который решает только третья ступень, — поэтому сценарий
# заморожен в tests/data и вместе с примером НЕ обновляется.
BUG016_CASE = Path(__file__).parent / "data" / "bug016_example14" / "config.json"


def _first_step(config_path, N=None, retries=None):
    """Первый шаг истории конфига через адаптер (с дроблением A-retry)."""
    cfg = load_config(config_path)
    if N is not None:
        cfg.grid.N = N
    if retries is not None:
        cfg.numerics.max_retries = retries
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    return sim, sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)


def _assert_restored(model):
    """Вне advance атрибуты запасного пути и третьей ступени — по умолчанию."""
    assert model._well_branch is None
    assert model._sg_lower_bound == -0.05
    assert model._line_search_l2 is False
    assert model._sg_step_max is None


# ═══════════════════════════════════════════════════════════
# A. Реальный Ньютон: шаги, которые без третьей ступени не проходят
# ═══════════════════════════════════════════════════════════

class TestFirstStepConverges:
    @pytest.mark.parametrize("N, sg0, p0_MPa", [
        (100, 0.224200, 6.196104),
        (150, 0.224420, 6.130659),
    ])
    def test_example14_fine_grid_first_step(self, N, sg0, p0_MPa):
        """Пример 14 версии BUG-016 (BUG016_CASE, R_s0 = 150), скачок p_wf 24.5 -> 6 МПа,
        сутки — без дробления.

        До фикса: RuntimeError после 512 подшагов (N = 100: 512 × 169 с;
        N = 150 не проходит и 4096 × 0.88 с). Замер плана BUG-016 (§1.4):
        S_g[0], p[0] ниже; N = 50 — 0.223531 / 6.392927 МПа (сходится и без
        третьей ступени). Допуски — порядка точности Ньютона.
        """
        _, res = _first_step(BUG016_CASE, N=N)
        assert res.n_substeps == 1
        assert res.state.Sg[0] == pytest.approx(sg0, abs=1e-5)
        assert res.state.p[0] == pytest.approx(p0_MPa * 1e6, abs=100.0)

    def test_04a_dense_grid_first_step(self):
        """04a, N = 200, шаг 300 с при ШТАТНОМ max_retries = 9 — без дробления.

        BUG-008: исходно нужно 4096 подшагов (12 удвоений) — при 9 отказ.
        Замер плана BUG-016 (§1.2): 1 подшаг; N = 300 — 2, N = 500 — 8.
        """
        _, res = _first_step(EXAMPLES_DIR / "04a_high_gas_saturation" / "config.json", N=200,
                             retries=NumericsConfig().max_retries)
        assert res.n_substeps == 1

    def test_example12_first_hour_not_split(self):
        """Пример 12, первый час — без дробления (DEBT-025: было 128 × 28.125 с)."""
        _, res = _first_step(EXAMPLES_DIR / "12_large_drainage_radius" / "config.json")
        assert res.n_substeps == 1

    def test_sg_step_limited_in_third_stage(self):
        """В третьей ступени |dS_g| между итерациями Ньютона <= 0.2.

        Пример 14 версии BUG-016 (BUG016_CASE), N = 100, первый суточный шаг
        прямо на модели прототипа: исходный путь и запасной отказывают, решает
        третья ступень. Приближения Ньютона — точки, где считается якобиан, и
        приближение, которое возвращает вызов (BUG-021: в сошедшемся приближении
        якобиан не строится). Они собираются по вызовам _newton_fixed_active_set
        (набор фаз внутри вызова фиксирован) и только при включённом ограничителе,
        то есть в третьей ступени. Замер плана BUG-021: 16 пар соседних
        приближений, без возвращённого — 13.
        """
        cfg = load_config(BUG016_CASE)
        cfg.grid.N = 100
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        _, dt = sim._schedule.substeps(0)
        model.set_bhp_control(cfg.time.history[0].p_wf / 1e5)   # Па -> бар

        calls = []
        orig_newton = model._newton_fixed_active_set
        orig_jac = model.finite_difference_jacobian

        def newton(z0, state_old, dt_s, gas_active, **kw):
            calls.append([])
            z, rep = orig_newton(z0, state_old, dt_s, gas_active, **kw)
            # Возвращённое приближение: якобиан в нём не строится (BUG-021), без
            # него последнее обновление каждого вызова выпало бы из проверки
            if model._sg_step_max is not None:
                calls[-1].append((z.copy(), gas_active.copy()))
            return z, rep

        def jac(z, state_old, dt_s, gas_active, **kw):
            if model._sg_step_max is not None:
                calls[-1].append((z.copy(), gas_active.copy()))
            return orig_jac(z, state_old, dt_s, gas_active, **kw)

        # Подмена на экземпляре: _advance_phases и _newton_fixed_active_set
        # вызывают self.<метод>, поэтому перехватываются оба
        model._newton_fixed_active_set = newton
        model.finite_difference_jacobian = jac
        s0 = BlackOilState(pressure_bar=init.p / 1e5, rs_sm3_sm3=init.Rs.copy(),
                           sg=init.Sg.copy(), gas_active=(init.regime == 1))
        _, rep = model.advance(s0, dt)
        assert rep.converged and rep.globalized

        n = model.grid.n
        # |dS_g| двухфазных ячеек между соседними итерациями одного вызова
        steps = [np.abs(b[0][n:][b[1]] - a[0][n:][a[1]]).max()
                 for seq in calls for a, b in zip(seq, seq[1:]) if b[1].any()]
        assert steps, "третья ступень не сделала ни одной итерации"
        assert max(steps) <= SG_STEP_MAX + 1e-12, f"max|dS_g| = {max(steps)}"
        _assert_restored(model)


# ═══════════════════════════════════════════════════════════
# B. Управляющая логика advance без Ньютона
# ═══════════════════════════════════════════════════════════

def _install_fake_phases3(model, plan):
    """Подменить _advance_phases; ключ — (ветка, граница S_g, ||F||_2 включён).

    plan[key] — (converged, p0_bar) или "raise". Возвращает список ключей вызовов
    и снимки (_sg_step_max) в момент каждого вызова.
    """
    calls, chop = [], []

    def fake(state_old, dt_s, max_active_iter, max_newton):
        key = (model._well_branch, model._sg_lower_bound, model._line_search_l2)
        calls.append(key)
        chop.append(model._sg_step_max)
        answer = plan[key]
        if answer == "raise":
            raise RuntimeError("искусственный отказ")
        converged, p0_bar = answer
        new = state_old.copy()
        new.pressure_bar[0] = p0_bar
        return new, BlackOilNewtonReport(converged, 3, 0.0)

    model._advance_phases = fake
    return calls, chop


ORIG3 = (None, -0.05, False)

# DEBT-030: отчёт исходного алгоритма в тестах ниже; у остальных ступеней — другие
# числа, чтобы было видно, чей отчёт вернул advance.
ORIG_REPORT = BlackOilNewtonReport(False, 15, 2.5e-7, 2, 21)


def _install_fake_reports(model, reports):
    """DEBT-030: как _install_fake_phases3, но у каждой ступени свой отчёт."""
    calls = []

    def fake(state_old, dt_s, max_active_iter, max_newton):
        key = (model._well_branch, model._sg_lower_bound, model._line_search_l2)
        calls.append(key)
        p0_bar, rep = reports[key]
        new = state_old.copy()
        new.pressure_bar[0] = p0_bar
        return new, replace(rep)   # копия: advance и _fallback меняют поля отчёта на месте

    model._advance_phases = fake
    return calls


class TestThirdStageLogic:
    """Модель p_wf = 150 бар, state_old = drawn_down (p[0] = 111.7 < 150):
    запасной путь стартует с «закрыта»."""

    def test_third_stage_after_fallback_fails(self, drawn_down):
        # Исходный и запасной (обе ветки) — отказ; третья ступень на «закрыта»
        # сходится с p[0] = 149 <= 150 — согласована.
        model = _model(150.0)
        calls, chop = _install_fake_phases3(model, {
            ORIG3: (False, 0.0), ("shut", None, False): (False, 0.0),
            ("open", None, False): (False, 0.0), ("shut", None, True): (True, 149.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False),
                         ("shut", None, True)]
        assert chop == [None, None, None, SG_STEP_MAX]
        assert rep.converged and rep.fallback and rep.globalized
        assert rep.well_branch == "shut"
        _assert_restored(model)

    def test_no_third_stage_when_fallback_converges(self, drawn_down):
        # Запасной путь BUG-014 сошёлся — третьей ступени нет, globalized = False
        model = _model(150.0)
        calls, _ = _install_fake_phases3(model, {
            ORIG3: (False, 0.0), ("shut", None, False): (False, 0.0),
            ("open", None, False): (True, 151.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False)]
        assert rep.converged and rep.fallback and not rep.globalized
        _assert_restored(model)

    def test_no_third_stage_when_original_converges(self, drawn_down):
        model = _model(150.0)
        calls, _ = _install_fake_phases3(model, {ORIG3: (True, 151.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3]
        assert not rep.fallback and not rep.globalized
        _assert_restored(model)

    def test_all_three_stages_fail(self, drawn_down):
        # Отказ везде: converged = False, globalized = True — адаптер раздробит шаг
        model = _model(150.0)
        plan = {k: (False, 0.0) for k in (ORIG3, ("shut", None, False), ("open", None, False),
                                          ("shut", None, True), ("open", None, True))}
        calls, _ = _install_fake_phases3(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert len(calls) == 5
        assert not rep.converged and rep.globalized
        _assert_restored(model)

    def test_all_fail_reports_original_newton(self, drawn_down):
        # DEBT-030 (A): отказ всех ступеней. Последняя попытка — ветка «открыта»
        # третьей ступени: «сошлась» за 0 итераций с невязкой 0, но несогласована
        # (p[0] = 140 < p_wf = 150). Так в T04 ведёт себя ветка «закрыта» на
        # неизменном начальном состоянии; до DEBT-030 её отчёт уходил в журнал шагов.
        # Ожидание: поля Ньютона (итерации, ||F||_inf, итерации набора фаз, смены
        # фаз) — исходного алгоритма; поля ветки — последней попытки, как раньше.
        model = _model(150.0)
        calls = _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
            ("shut", None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9)),
            ("open", None, True): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0))})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False),
                         ("shut", None, True), ("open", None, True)]
        assert not rep.converged
        assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                rep.phase_switches) == (15, 2.5e-7, 2, 21)
        assert rep.fallback and rep.globalized
        assert (rep.well_branch, rep.well_switches) == ("open", 1)
        _assert_restored(model)

    def test_all_fail_rate_control_reports_original_newton(self):
        # DEBT-030 (B): управление по дебиту. Запасной путь — повтор без ветки
        # (ключ (None, None, ·)), третья ступень — то же с ||F||_2. Последняя
        # попытка — настоящий отказ Ньютона, но правило то же: поля Ньютона —
        # исходного алгоритма; ветки нет ('', 0 смен).
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        calls = _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            (None, None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            (None, None, True): (0.0, BlackOilNewtonReport(False, 13, 4.0e-5, 4, 9))})
        _, rep = model.advance(state, 60.0)
        assert calls == [ORIG3, (None, None, False), (None, None, True)]
        assert not rep.converged
        assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                rep.phase_switches) == (15, 2.5e-7, 2, 21)
        assert rep.fallback and rep.globalized
        assert (rep.well_branch, rep.well_switches) == ("", 0)
        _assert_restored(model)

    def test_converged_third_stage_keeps_own_report(self, drawn_down):
        # DEBT-030 (C): замена полей — только при общем отказе. Третья ступень
        # сошлась на «закрыта» (p[0] = 149 <= 150 — согласована): отчёт её
        # собственный (17 итераций), не исходного алгоритма. Регрессия прототипа
        # ошибку здесь не видит: _grow_dt различает только iterations >= 10 и >= 6,
        # а 17 и 15 дают один и тот же следующий шаг.
        model = _model(150.0)
        calls = _install_fake_reports(model, {
            ORIG3: (0.0, ORIG_REPORT),
            ("shut", None, False): (0.0, BlackOilNewtonReport(False, 14, 3.0e-6, 3, 7)),
            ("open", None, False): (140.0, BlackOilNewtonReport(True, 0, 0.0, 1, 0)),
            ("shut", None, True): (149.0, BlackOilNewtonReport(True, 17, 2.0e-16, 2, 15))})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False),
                         ("shut", None, True)]
        assert rep.converged
        assert (rep.iterations, rep.residual_inf, rep.active_set_iterations,
                rep.phase_switches) == (17, 2.0e-16, 2, 15)
        assert rep.fallback and rep.globalized
        assert (rep.well_branch, rep.well_switches) == ("shut", 0)
        _assert_restored(model)

    def test_exception_in_third_stage(self, drawn_down):
        # Исключение в третьей ступени пробрасывается; атрибуты — по умолчанию
        model = _model(150.0)
        _install_fake_phases3(model, {
            ORIG3: (False, 0.0), ("shut", None, False): (False, 0.0),
            ("open", None, False): (False, 0.0), ("shut", None, True): "raise"})
        with pytest.raises(RuntimeError):
            model.advance(drawn_down, 3600.0)
        _assert_restored(model)

    def test_rate_control_third_stage(self):
        # Управление по дебиту: запасной путь без ветки; третья ступень — тот же
        # повтор с ||F||_2 и ограничителем
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        calls, chop = _install_fake_phases3(model, {
            ORIG3: (False, 0.0), (None, None, False): (False, 0.0),
            (None, None, True): (True, 190.0)})
        _, rep = model.advance(state, 60.0)
        assert calls == [ORIG3, (None, None, False), (None, None, True)]
        assert chop == [None, None, SG_STEP_MAX]
        assert rep.converged and rep.globalized
        _assert_restored(model)
