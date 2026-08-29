"""ABC EnergySolver — абстрактный тепловой солвер.

Один шаг: (hydro_result, state_prev, dt, T_ext) → T_new[N].
Splitting: T решается при замороженных p, Sg, Rs из hydro_result.
"""

from abc import ABC, abstractmethod

import numpy as np

from ..state import HydroResult, SimulationState


class EnergySolver(ABC):
    """Абстрактный тепловой солвер.

    Конкретная реализация: TridiagEnergySolver (прогонка Томаса).
    """

    @abstractmethod
    def solve(self, hydro_result: HydroResult,
              state_prev: SimulationState,
              dt: float, T_ext: float) -> np.ndarray:
        """Один шаг теплопереноса: T^n → T^{n+1}.

        Аргументы:
            hydro_result — результат гидро-шага: state(p^{n+1}, Sg, Rs),
                           потоки Q_o, Q_g, G_o на гранях [N+1]
            state_prev   — состояние на предыдущем шаге (T^n, p^n, Rs^n)
            dt           — шаг по времени, с
            T_ext        — температура на контуре питания (Дирихле), К

        Возвращает:
            T_new — массив [N], температура в центрах ячеек, К
        """
        ...
