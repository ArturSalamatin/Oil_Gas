"""ABC HydroSolver — абстрактный гидродинамический солвер.

Определяет контракт: один шаг гидродинамики state^n → state^{n+1}.
HydroResult определён в state.py (не здесь), чтобы избежать
циклических зависимостей с SimulationHistory.
"""

from abc import ABC, abstractmethod

from ..state import SimulationState, HydroResult, BoundaryConditions


class HydroSolver(ABC):
    """Абстрактный гидродинамический солвер.

    Один шаг: (state, dt, bc) → HydroResult.
    Конкретные реализации:
      - AnalyticalHydroSolver (заглушка, стационарный профиль)
      - PrototypeHydroAdapter (обёртка прототипа коллеги)
      - NewtonHydroSolver (собственный блочный Ньютон, будущее)
    """

    @abstractmethod
    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        """Один шаг гидродинамики: state^n → state^{n+1}.

        Аргументы:
            state — текущее состояние (p, Sg, Rs, T, regime, t)
            dt — шаг по времени, с (определяется Simulator)
            bc — граничные условия (well: WellControl, p_ext, Rs_ext, ...)

        Возвращает:
            HydroResult — обновлённое состояние + потоки через грани (11 массивов [N+1])

        HydroSolver обновляет p, Sg, Rs, regime. T не трогает (splitting:
        температуру обновляет EnergySolver отдельно).
        """
        ...
