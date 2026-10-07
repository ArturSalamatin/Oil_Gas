"""ABC EnergySolver — абстрактный тепловой солвер.

Один шаг: (hydro_result, state_prev, dt, bc) → T_new[N].
Splitting: T решается при замороженных p, Sg, Rs из hydro_result.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from ..state import BoundaryConditions, HydroResult, SimulationState

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
              dt: float, bc: BoundaryConditions,
              collect: "EnergyBalanceAccumulator | None" = None) -> np.ndarray:
        """Один шаг теплопереноса: T^n → T^{n+1}.

        Аргументы:
            hydro_result — результат гидро-шага: state(p^{n+1}, Sg, Rs),
                           потоки Q_o, Q_g, G_o на гранях [N+1]
            state_prev   — состояние на предыдущем шаге (T^n, p^n, Rs^n)
            dt           — шаг по времени, с
            bc           — граничные условия на контуре: T_ext (Дирихле по T),
                           Rs_ext (состав притока, eq. bc_Sg_ext) и p_ext —
                           при втекании через грань N свойства фаз берутся
                           при условиях контура (eq. bc_props_ext, DEBT-017).
                           Передаётся объектом целиком — как в
                           HydroSolver.solve (DEBT-009)
            collect      — накопитель баланса энергии (DEBT-013), опционально

        Возвращает:
            T_new — массив [N], температура в центрах ячеек, К

        Если collect задан, реализация ОБЯЗАНА вызвать
        collect.add_substep(...) с теми же коэффициентами, которые пошли
        в СЛАУ, и collect.add_accumulation(...) после решения системы.
        Пересчитывать коэффициенты заново нельзя: расхождение баланса
        со схемой породило BUG-004.

        Температуры накопителю можно передавать от любой общей опоры (T_ext
        в add_substep, T_new и T_prev в add_accumulation): все члены баланса —
        разности температур или от T не зависят. TridiagEnergySolver передаёт
        отклонения от T_ext (DEBT-043).
        """
        ...
