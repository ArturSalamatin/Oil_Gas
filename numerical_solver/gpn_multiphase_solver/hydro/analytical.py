"""AnalyticalHydroSolver — заглушка с аналитическим стационарным решением.

Однофазный стационарный поток нефти:
  p(r) = p_wf + (p_ext - p_wf) · ln(r/rw) / ln(R/rw)
  Sg = 0, Rs = Rs_ext, regime = 2 (однофазное)

Потоки вычисляются через compute_fluxes() — не дублирует логику.
Не зависит от dt (стационар устанавливается мгновенно).
Температуру не трогает (splitting: T обновляется в EnergySolver).

Назначение:
  - Тестирование EnergySolver на известном поле давления
  - Тестирование Simulator (полный цикл)
  - Валидация VAL-001 (аналитическое T(r) при известном p(r))
"""

import numpy as np

from .base import HydroSolver
from ..state import SimulationState, HydroResult, BoundaryConditions
from ..grid.base import Grid
from ..pvt.base import HydroPVT, RelPermModel
from ..fluxes import compute_fluxes


class AnalyticalHydroSolver(HydroSolver):
    """Стационарный логарифмический профиль давления (однофазный)."""

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

        # Забойное давление из стратегии управления
        p_wf = bc.well.boundary_pressure(state, grid, self._pvt, self._relperm)

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
