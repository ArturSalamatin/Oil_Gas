"""DEBT-055, аудит 1: тесты плана (шаги 2, 4) на коде с правками плана в памяти (conftest.py).

Новые тесты — дословно из плана; расширенные тесты DEBT-054 — копии с добавками плана.
Ожидание: DEBT055_PATCH=all — всё passed; proto — 5 failed (тексты адаптера: 3 случая
test_failure_details, реальный текст, текст Simulator); none — падают и тесты отчёта.
"""
import numpy as np
import pytest

from gpn_multiphase_solver.hydro import prototype_adapter as adapter_mod
from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from radial_blackoil.blackoil import BlackOilNewtonReport

from tests.test_prototype_activation_cap import _sim
from tests.test_prototype_cell_tolerance import (  # noqa: F401
    _build as _nabor, CELL_TOL, DT, DT_STAGE4, shutin)
from tests.test_prototype_failure_diagnostics import _bug018_model, _THRESHOLD
from tests.test_prototype_globalization import ORIG3, _install_fake_reports
from tests.test_prototype_well_branch import _model, drawn_down  # noqa: F401


class TestRoundoffFloor:
    """DEBT-055: отчёт отказа несёт cell_floor — меру ячеек вектора |J|·ulp(z) (eq:newton_cell_floor)."""

    def test_definition_at_linear_solver_exit(self, monkeypatch):
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
        model, state = _nabor(12, cell_tol=CELL_TOL)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)
        assert rep.converged and rep.cell_floor is None
        model, state = _nabor(12)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active,
                                                max_iter=1)
        assert not rep.converged and rep.cell_floor is None

    def test_bug018_failure_at_floor(self):
        model, ps, dt = _bug018_model()
        _, rep = model._advance_phases(ps, dt)
        assert not rep.converged and rep.exit_reason == "line_search"
        assert CELL_TOL < rep.cell_measure <= rep.cell_floor
        assert rep.cell_floor == pytest.approx(6.42e-8, rel=1e-3)

    def test_floor_proportional_to_dt(self):
        model, ps, dt = _bug018_model()
        _, full = model._advance_phases(ps, dt)
        _, half = model._advance_phases(ps, dt / 2)
        assert not half.converged and half.cell_measure > CELL_TOL
        assert half.cell_floor / full.cell_floor == pytest.approx(0.5, rel=1e-3)

    def test_switching_limit_stops_at_floor(self, shutin):
        model, ps = shutin
        try:
            model.cell_tol = 1e-30
            _, rep = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert not rep.converged and rep.exit_reason == "max_iter"
        assert rep.cell_measure <= rep.cell_floor
        assert rep.cell_floor == pytest.approx(4.34e-11, rel=1e-2)


def test_switching_converged_report_none(shutin):
    """Копия TestSwitching.test_converged_report с добавкой плана (шаг 2, п. 2)."""
    model, ps = shutin
    _, rep = model._newton_switching(ps, DT_STAGE4)
    assert rep.converged and rep.exit_reason == "converged"
    assert rep.cell_floor is None


def test_total_failure_carries_floor(drawn_down):
    """Копия test_total_failure_carries_original_diagnostics с добавками плана (шаг 2, п. 3)."""
    model = _model(150.0)
    orig = BlackOilNewtonReport(False, 4, 6.5e-15, 2, 21, residual_tol=5.4e-7,
                                cell_measure=2.6e-8, exit_reason="line_search", cell_floor=6.4e-8)
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
    assert rep.cell_floor == 6.4e-8


def _rep(res, tol=None, meas=None, reason="", floor=None):
    """Отчёт отказа с полями DEBT-054 (и предела DEBT-055) — шаг 4, п. 1 плана."""
    return BlackOilNewtonReport(False, 3, res, residual_tol=tol, cell_measure=meas,
                                exit_reason=reason, cell_floor=floor)


def test_failure_details_new_cases():
    """Три новых случая test_failure_details (шаг 4, п. 2) — строки плана дословно."""
    cases = [
        (_rep(1e-15, 1e-9, 3e-8, "line_search", 6e-8), 1e-8, 1,
         " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", предел округления 6.00e-08, "
         "выход: линейный поиск не принял ни одной точки — не выполнено только условие по ячейке, "
         "мера не выше предела округления (он пропорционален шагу); числа — Ньютона ступени 1"),
        (_rep(1e-15, 1e-9, 3e-8, "max_iter", 1e-9), 1e-8, 4,
         " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", предел округления 1.00e-09, "
         "выход: исчерпан лимит итераций — не выполнено только условие по ячейке; числа — Ньютона ступени 4"),
        (_rep(1e-3, 1e-9, 1.0, "max_iter", 1e-9), 1e-8, 1,
         " (допуск 1.00e-09), мера ячеек 1.00e+00" + _THRESHOLD + ", предел округления 1.00e-09, "
         "выход: исчерпан лимит итераций — не выполнены оба условия сходимости; числа — Ньютона ступени 1"),
    ]
    for report, cell_tol, stage, expected in cases:
        assert adapter_mod._failure_details(report, cell_tol, stage) == expected


def test_adapter_message_cell_test_only_parts():
    """Копия test_adapter_message_cell_test_only с частями плана (шаг 4, п. 3)."""
    sim, init, dt = _sim(N=350)
    with pytest.raises(HydroConvergenceError) as exc:
        sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
    msg = str(exc.value)
    print("\nТЕКСТ ОТКАЗА:", msg)
    assert msg.startswith("advance не сошёлся: dt = 8.640e+04 с, t = 0.0000 сут, "
                          "итераций 4, невязка 6.51e-15 (допуск ")
    for part in ("мера ячеек ", "(порог numerics.newton_cell_tol = 1e-08)",
                 "выход: линейный поиск не принял ни одной точки",
                 " — не выполнено только условие по ячейке",
                 ", предел округления 6.42e-08",
                 ", мера не выше предела округления (он пропорционален шагу)"):
        assert part in msg
    assert msg.endswith("; числа — Ньютона ступени 1")


def test_simulator_message_tail():
    """Копия test_simulator_message_ends_with_adapter_text с добавкой плана (шаг 4, п. 4)."""
    sim, init, _ = _sim(N=350, retries=0)
    with pytest.raises(RuntimeError) as exc:
        sim.run(init)
    tail = str(exc.value).split("Последний отказ гидродинамики: ", 1)[1]
    assert tail == str(exc.value.__cause__)
    assert "мера не выше предела округления" in tail
