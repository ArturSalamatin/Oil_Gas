"""ABC HydroSolver — абстрактный гидродинамический солвер.

Определяет контракт: один шаг гидродинамики state^n → state^{n+1}.
HydroResult определён в state.py (не здесь), чтобы избежать
циклических зависимостей с SimulationHistory.
"""

from abc import ABC, abstractmethod

from ..state import SimulationState, HydroResult, BoundaryConditions


class HydroConvergenceError(RuntimeError):
    """Шаг гидродинамики не сошёлся при данном dt; шаг дробит Simulator (DEBT-015)."""


class HydroSolver(ABC):
    """Абстрактный гидродинамический солвер.

    Один шаг: (state, dt, bc) → HydroResult.
    Конкретные реализации:
      - PrototypeHydroAdapter (обёртка прототипа коллеги)
      - NewtonHydroSolver (собственный блочный Ньютон, будущее)

    Тестовый двойник LogProfileHydroStub (tests/_doubles.py) намеренно
    держится вне пакета: он подставляет готовый лог-профиль вместо решения
    уравнения фильтрации и не должен попадать в production-расчёт (DEBT-005).

    Запас компонентов для баланса массы — component_inventories (DEBT-039).
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

        Один шаг без дробления (DEBT-015). Не сошёлся — HydroConvergenceError,
        состояние не меняется; дробит шаг Simulator, чтобы энергия и балансы
        шли ровно по принятым подшагам (BUG-010).

        Принятое состояние проверяет Simulator (DEBT-075): 0 ≤ Sg ≤ 1,
        p > 0, Rs ≥ 0, все конечны — точно, без допуска; иначе расчёт
        обрывается RuntimeError. Малые отрицательные Sg решатель обнуляет
        сам, как прототип.
        """
        ...

    def component_inventories(self, state: SimulationState) -> tuple[float, float] | None:
        """Запас нефтяного и газового компонентов, м³ст. Ур. (eq:residual_oil), (eq:residual_gas)."""
        # None — решатель массу не сохраняет. Не абстрактный (DEBT-039):
        # тестовые двойники (tests/_doubles.py) уравнения фильтрации не
        # решают и массу не сохраняют — баланс массы для них не считается.
        # Решатель, сохраняющий массу, обязан переопределить метод И заполнять
        # HydroResult.int_G_*: иначе Simulator бросит RuntimeError на первом
        # шаге (mass_balance.py).
        return None
