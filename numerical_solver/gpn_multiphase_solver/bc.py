"""Граничные условия: ABC WellControl и реализация PressureControl."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from .state import SimulationState
    from .grid.base import Grid
    from .pvt.base import HydroPVT, RelPermModel


class WellControl(ABC):
    """Стратегия управления скважиной на одном интервале истории."""

    @abstractmethod
    def boundary_pressure(self, state: SimulationState,
                          grid: Grid, pvt: HydroPVT,
                          relperm: RelPermModel) -> float:
        """Давление на забойной грани, Па."""
        ...


class PressureControl(WellControl):
    """Задано забойное давление p_wf = const."""

    def __init__(self, p_wf: float):
        if p_wf <= 0:
            raise ValueError(f"p_wf должно быть > 0, получено {p_wf}")
        self._p_wf = float(p_wf)

    @property
    def p_wf(self) -> float:
        return self._p_wf

    def boundary_pressure(self, state, grid, pvt, relperm) -> float:
        return self._p_wf
