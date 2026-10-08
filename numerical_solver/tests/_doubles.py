"""Тестовые двойники для gpn_multiphase_solver.

LogProfileHydroStub — НЕ решатель. Подставляет заранее известный
стационарный логарифмический профиль давления вместо решения уравнения
фильтрации. Существует только ради детерминированности: тесты энергии,
Simulator и вывода нуждаются в точно известном p(r), чтобы изолировать
проверяемый эффект от гидродинамики.

Жил в gpn_multiphase_solver/hydro/analytical.py до DEBT-005. Вынесен в
tests/, чтобы его нельзя было по ошибке подставить в production-расчёт
(сигнатура совпадает с настоящим PrototypeHydroAdapter).
"""

import numpy as np

from gpn_multiphase_solver.hydro.base import HydroSolver, HydroConvergenceError
from gpn_multiphase_solver.state import (
    SimulationState, HydroResult, BoundaryConditions)
from gpn_multiphase_solver.grid.base import Grid
from gpn_multiphase_solver.pvt.base import HydroPVT, RelPermModel
from gpn_multiphase_solver.fluxes import compute_fluxes


class LogProfileHydroStub(HydroSolver):
    """Стационарный логарифмический профиль давления (однофазный).

    Тестовый двойник, не решатель. См. модульный docstring.
    """

    def __init__(self, grid: Grid, pvt: HydroPVT, relperm: RelPermModel):
        self._grid = grid
        self._pvt = pvt
        self._relperm = relperm

    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        """Построить стационарный профиль и вычислить потоки.

        Результат не зависит от dt и от входного state.p —
        давление вычисляется аналитически из p_wf и p_ext.
        dt влияет только на state.t.
        """
        grid = self._grid
        N = grid.N

        # Забойное давление из стратегии управления: двойник — модуль
        # гидродинамики, он сам читает управление (только PressureControl)
        p_wf = bc.well.p_wf

        # Логарифмический профиль давления (точное решение стационарного
        # уравнения фильтрации при постоянных свойствах)
        log_ratio = np.log(grid.r_centers / grid.r_well) / np.log(grid.R_ext / grid.r_well)
        p = p_wf + (bc.p_ext - p_wf) * log_ratio

        # Однофазное состояние: Sg=0, Rs=Rs_ext, regime=2
        new_state = SimulationState(
            p=p,
            Sg=np.zeros(N),
            Rs=np.full(N, bc.Rs_ext),
            T=state.T.copy(),                     # гидро не трогает T
            regime=np.full(N, 2, dtype=int),
            t=state.t + dt,
        )

        # Потоки — через compute_fluxes (единая логика upstream, знаков, формул)
        result = compute_fluxes(new_state, grid, self._pvt, self._relperm, bc)

        # compute_fluxes возвращает HydroResult с state=new_state (без изменений),
        # что и нужно: state содержит обновлённые p, Sg, Rs, T, t.
        return result


class FailingHydroStub(HydroSolver):
    """Двойник, отказывающий на заданных подшагах, — проверка локального дробления (DEBT-015)."""

    # Физика — у внутреннего двойника. fails(state, dt) → True — бросить
    # HydroConvergenceError, как PrototypeHydroAdapter при несошедшемся
    # advance. Запоминает dt каждого вызова solve, включая отказавшие, —
    # тест по этому списку проверяет последовательность подшагов.

    def __init__(self, inner: HydroSolver, fails):
        self._inner = inner
        self._fails = fails
        self.dt_calls: list[float] = []      # dt каждого вызова solve

    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        self.dt_calls.append(dt)
        if self._fails(state, dt):
            raise HydroConvergenceError(
                f"двойник: отказ при dt = {dt:g} с, t = {state.t:g} с")
        return self._inner.solve(state, dt, bc)

    def component_inventories(self, state: SimulationState):
        """Запас — у внутреннего двойника (DEBT-039)."""
        # Без делегирования метод ABC вернул бы None, и Simulator не вёл бы
        # баланс массы на обёрнутом двойнике с интегралами (test_mass_balance.py).
        return self._inner.component_inventories(state)
