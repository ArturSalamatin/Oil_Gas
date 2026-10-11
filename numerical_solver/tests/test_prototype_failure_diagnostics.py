"""DEBT-054: отчёт Ньютона прототипа называет причину отказа, текст отказа — какое условие не выполнено.

После BUG-022 решение Ньютона принимается, только если выполнены абсолютный критерий
||F||_inf <= atol + rtol*max(||F_0||_inf, 1e-9) и условие по ячейке
max_c |F_c,i|*dt/PV_i <= cell_tol. Решение, отвергнутое только условием ячейки, выглядело
в отчёте как «итераций 4, невязка 6.51e-15, не сошлось» (BUG-018 при N = 350, шаг
86400 с): ни допуска, ни меры ячеек, ни причины выхода (линейный поиск встал на пределе
округления). Теперь отчёт несёт residual_tol, cell_measure (на той же невязке, что
residual_inf) и exit_reason; адаптер печатает их и какое условие не выполнено; Simulator
дописывает текст адаптера в свой при исчерпании дробления. Отказ ступени 4 пишет число
выполненных итераций, а не max_iter (DEBT-061, поглощена DEBT-054).

План: vault/plans/debt-054 newton-failure-diagnostics.md; замеры —
vault/issues/debt-054/probes/failure_census.out.txt, test_scenarios.out.txt.
"""

import numpy as np
import pytest

from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.units import BAR_TO_PA
from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.state import BlackOilState

from .test_prototype_activation_cap import _sim
from .test_prototype_cell_tolerance import (  # noqa: F401
    _build as _nabor, _measure, CELL_TOL, DT, DT_STAGE4, shutin)
from .test_prototype_globalization import ORIG3, _install_fake_reports
from .test_prototype_well_branch import _model, drawn_down  # noqa: F401

ATOL, RTOL = 1e-11, 1e-8      # умолчания обоих Ньютонов прототипа (atol_sm3s, rtol)


def _tol(model, z0, s_old, dt, mask):
    """Абсолютный допуск Ньютона: atol + rtol*max(||F(z0)||_inf, 1e-9) — те же операции, что в прототипе."""
    f0 = model.residual(z0, s_old, dt, mask)
    return ATOL + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)


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
