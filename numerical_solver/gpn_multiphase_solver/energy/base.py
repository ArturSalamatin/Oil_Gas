"""ABC EnergySolver — абстрактный тепловой солвер.

Один шаг: (hydro_result, state_prev, dt, T_ext) → T_new[N].
Splitting: T решается при замороженных p, Sg, Rs из hydro_result.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from ..state import HydroResult, SimulationState

if TYPE_CHECKING:
    # Только для аннотации: в рантайме base.py не импортирует balance.py,
    # чтобы не заводить лишнюю связь внутри пакета energy/.
    from .balance import EnergyBalanceAccumulator


class EnergySolver(ABC):
    """Абстрактный тепловой солвер.

    Конкретная реализация: TridiagEnergySolver (прогонка Томаса).
    """

    @abstractmethod
    def solve(self, hydro_result: HydroResult,
              state_prev: SimulationState,
              dt: float, T_ext: float,
              collect: "EnergyBalanceAccumulator | None" = None) -> np.ndarray:
        """Один шаг теплопереноса: T^n → T^{n+1}.

        Аргументы:
            hydro_result — результат гидро-шага: state(p^{n+1}, Sg, Rs),
                           потоки Q_o, Q_g, G_o на гранях [N+1]
            state_prev   — состояние на предыдущем шаге (T^n, p^n, Rs^n)
            dt           — шаг по времени, с
            T_ext        — температура на контуре питания (Дирихле), К
            collect      — накопитель баланса энергии (DEBT-013), опционально

        Возвращает:
            T_new — массив [N], температура в центрах ячеек, К

        Если collect задан, реализация ОБЯЗАНА вызвать
        collect.add_substep(...) с теми же коэффициентами, которые пошли
        в СЛАУ, и collect.add_accumulation(...) после решения системы.
        Пересчитывать коэффициенты заново нельзя: расхождение баланса
        со схемой породило BUG-004.
        """
        ...
