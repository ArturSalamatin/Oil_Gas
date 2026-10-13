"""BUG-025: допуск Ньютона прототипа не ниже предела округления накопления — короткий шаг останова сходится.

Невязка прототипа — в м³ст/с: накопление (M^{n+1} - M^n)/Δt, каждый запас — с ошибкой
округления ~ε_маш·M. Ниже ~ε_маш·M_max/Δt невязка не опускается, и на коротком шаге это
больше абсолютного допуска 1e-11 м³ст/с (граница — от ~0.01–0.05 с при N = 350 до ~0.5 с
при N = 50: растёт с крупнейшей ячейкой). На старте останова после 10 сут добычи
(bug020_rs150, M_max = 7.2e3 м³ст) линейный поиск вставал при |F|·Δt = 5–7e-13 м³ст,
отказывали все четыре ступени advance, дробление до dt/512 не помогало. Теперь допуск —
max(1e-11, κ·ε_маш·M_max/Δt) + 1e-8·max(‖F₀‖, 1e-9), κ = 4 (Ур. (eq:newton_abs_tol)
problem_statement.tex); M_max — наибольший запас ячейки старого слоя (нефть; газ / s_g).

План: vault/plans/bug-025 short-step-residual-floor.md; замеры —
vault/issues/bug-025/probes/*.out.txt.
"""

import copy
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S
from radial_blackoil import blackoil
from radial_blackoil.state import BlackOilState

CFG = Path(__file__).parent / "data" / "bug020_rs150" / "config.json"
N_PROD = 10                       # интервалов добычи в конфиге, по 1 сут
ATOL, RTOL = 1e-11, 1e-8          # умолчания обоих Ньютонов прототипа (atol_sm3s, rtol)
EPS = float(np.finfo(float).eps)
SHORT_DTS = (1e-2, 1e-3, 1e-4)    # до BUG-025 все три — отказ всех ступеней advance


def _m_max(model, state):
    """M_max теми же операциями, что _absolute_tol прототипа: нефть и газ / s_g старого слоя, м³ст."""
    oi0, gi0 = model._old_inventories(state)
    return max(float(np.max(np.abs(oi0))), float(np.max(np.abs(gi0))) / model.gas_residual_scale)


def _tol(model, state, dt):
    """Допуск Ньютона из старого состояния по Ур. (eq:newton_abs_tol) — те же операции, что в прототипе."""
    z0 = model.pack(state)
    f0 = model.residual(z0, state, dt, state.gas_active)
    floor = max(ATOL, blackoil.ROUNDOFF_KAPPA * EPS * _m_max(model, state) / float(dt))
    return floor + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)


@pytest.fixture(scope="module")
def shutin():
    """Модель фабрики и состояние прототипа на конец 10 сут добычи; управление — останов q_oil = 0 (~1 с)."""
    cfg = load_config(CFG)
    shut = cfg.time.history[N_PROD]
    cfg.time.history = cfg.time.history[:N_PROD]
    sim, s0 = SimulatorFactory.from_config(cfg)
    st = sim.run(s0).states[-1]
    model = sim._hydro._model
    # Управление — как ставит адаптер перед advance (prototype_adapter.solve, шаг 1): м³ст/сут, бар
    model.set_oil_rate_control(shut.q_oil * DAY_TO_S, shut.min_bhp / BAR_TO_PA)
    ps = BlackOilState(pressure_bar=st.p / BAR_TO_PA, rs_sm3_sm3=st.Rs.copy(),
                       sg=st.Sg.copy(), gas_active=(st.regime == 1))
    return model, ps


# ═══════════════════════════════════════════════════════════
# A. Формула допуска
# ═══════════════════════════════════════════════════════════

class TestToleranceFloor:
    """Предел округления включается только на коротком шаге; на обычном допуск прежний побитово."""

    def test_long_step_tolerance_unchanged(self, shutin):
        """Δt = 3600 с: κ·ε·M_max/Δt = 1.8e-15 < 1e-11 — допуск atol + rtol·‖F₀‖, как до BUG-025, побитово.

        Ловит: предел, сложенный с atol вместо max (допуск сдвинулся бы на всех шагах,
        истории примеров — не побитово).
        """
        model, ps = shutin
        dt = 3600.0
        f0 = model.residual(model.pack(ps), ps, dt, ps.gas_active)
        _, rep = model._newton_fixed_active_set(model.pack(ps), ps, dt, ps.gas_active)
        assert rep.residual_tol == ATOL + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)

    def test_short_step_tolerance_floor(self, shutin):
        """Δt = 1e-3 с: допуск — по Ур. (eq:newton_abs_tol), 6.43e-9 против 3.98e-11 без предела (замер).

        Ловит: M_max не по старому слою, газовые строки без деления на s_g, другой κ,
        предел только в одной из функций Ньютона.
        """
        model, ps = shutin
        dt = 1e-3
        _, rep = model._newton_fixed_active_set(model.pack(ps), ps, dt, ps.gas_active)
        assert rep.residual_tol == _tol(model, ps, dt)
        assert rep.residual_tol > 100 * ATOL


# ═══════════════════════════════════════════════════════════
# B. Первый шаг останова
# ═══════════════════════════════════════════════════════════

class TestShortShutinStep:
    """Первый шаг останова 1e-2…1e-4 с из конца добычи (332 двухфазных ячейки, max S_g = 0.441)."""

    @pytest.mark.parametrize("dt", SHORT_DTS)
    def test_first_stage_converges(self, shutin, dt):
        """advance сходится первой ступенью; ошибка массы за шаг не больше κ·ε·M_max.

        Замер (fix_k4_r200.out.txt): 3, 2, 2 итерации, |F|·Δt = 1.07e-12, 1.12e-12,
        8.95e-13 м³ст при κ·ε·M_max = 6.4e-12. До исправления — отказ всех ступеней,
        ступень 1 — выход 'line_search' (scan_r200.out.txt).
        """
        model, ps = shutin
        _, rep = model.advance(ps.copy(), dt)
        assert rep.converged and rep.exit_reason == "converged"
        assert not rep.fallback and not rep.phase_switching
        assert rep.residual_inf <= rep.residual_tol
        assert rep.residual_inf * dt <= blackoil.ROUNDOFF_KAPPA * EPS * _m_max(model, ps)

    def test_fourth_stage_short_step(self, shutin):
        """Ступень 4 отдельно (её зовёт адаптер по памяти, DEBT-048) на Δt = 1e-3 с сходится с тем же допуском.

        Замер (stage4_short.out.txt): 2 итерации, допуск 6.429e-9; до исправления —
        40 итераций на пределе, выход 'max_iter'. Ловит предел только в ступенях 1–3.
        """
        model, ps = shutin
        dt = 1e-3
        _, rep = model.advance_fourth_stage(ps.copy(), dt)
        assert rep.converged and rep.exit_reason == "converged" and rep.phase_switching
        assert rep.residual_tol == _tol(model, ps, dt)


# ═══════════════════════════════════════════════════════════
# C. Simulator: останов короткими интервалами
# ═══════════════════════════════════════════════════════════

class TestShortShutinIntervals:
    """10 сут добычи + 16 интервалов останова по dt: каждый — один шаг, без отказов гидродинамики."""

    @pytest.mark.parametrize("dt", [3600.0 / 2 ** 16, 0.01])
    def test_no_hydro_failures(self, dt):
        """dt = 3600/2**16 = 0.0549 с — первый шаг серии k = 7 VAL-004; 0.01 с.

        До исправления (repro_nabor.out.txt): отказ гидродинамики на 5-м шаге (0.0549 с; к
        тому времени приток к забою спал, ‖F₀‖ и с ним допуск упали до 1.33e-11) и на
        первом (0.01 с), дробление до dt/512 не помогало, расчёт падал. После: 0 отказов.
        """
        cfg = load_config(CFG)
        prod, shut = cfg.time.history[:N_PROD], cfg.time.history[N_PROD]
        tail = []
        for _ in range(16):
            x = copy.deepcopy(shut)
            x.dt = dt
            tail.append(x)
        cfg.time.history = list(prod) + tail
        # dt_integration = 1 сут длиннее интервала: каждый интервал — один шаг, если сошёлся
        assert cfg.time.dt_integration > dt
        sim, s0 = SimulatorFactory.from_config(cfg)
        fails = []
        solve = sim._hydro.solve

        def counting(state, h, bc):
            try:
                return solve(state, h, bc)
            except HydroConvergenceError:
                fails.append((state.t, h))
                raise

        sim._hydro.solve = counting
        hist = sim.run(s0)
        assert fails == []
        assert len(hist.times) == 1 + N_PROD + 16
        # время копится сложением t + dt: ulp(8.64e5 с) = 1.2e-10, 16 сложений — до ~1e-9
        assert hist.times[-1] == pytest.approx(N_PROD * DAY_TO_S + 16 * dt, abs=1e-6)
