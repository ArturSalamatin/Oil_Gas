"""Контейнеры данных: состояние, результаты, граничные условия, история."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .bc import WellControl


# ── Состояние симуляции ──────────────────────────────────────

@dataclass
class SimulationState:
    """Полное состояние системы в момент времени t."""
    p: np.ndarray
    Sg: np.ndarray
    Rs: np.ndarray
    T: np.ndarray
    regime: np.ndarray
    t: float


# ── Результат гидродинамического шага ────────────────────────

@dataclass
class HydroResult:
    """Потоки через грани после гидро-шага. Все массивы [N+1]."""
    state: SimulationState
    # Покомпонентные объёмные потоки (ст. условия)
    G_o: np.ndarray
    G_g: np.ndarray
    G_free_gas: np.ndarray
    # Фазовые объёмные расходы (пл. условия)
    Q_o: np.ndarray
    Q_g: np.ndarray
    # Скорости фильтрации
    u_o: np.ndarray
    u_g: np.ndarray
    # Фазовые массовые расходы
    m_o: np.ndarray
    m_g: np.ndarray
    # Покомпонентные массовые расходы
    Gm_o: np.ndarray
    Gm_g: np.ndarray


# ── Результат теплового шага ─────────────────────────────────

@dataclass
class EnergyResult:
    """Температура после теплового шага."""
    T_new: np.ndarray


# ── Скважинные данные ────────────────────────────────────────

@dataclass
class WellData:
    """Скважинные параметры на одном сохранённом шаге."""
    q_o_std: float
    q_g_std: float
    m_o_well: float
    m_g_well: float
    p_wf: float
    T_wf: float


# ── Граничные условия ────────────────────────────────────────

@dataclass
class BoundaryConditions:
    """Полный набор граничных условий на текущем шаге."""
    well: WellControl
    p_ext: float
    T_ext: float
    Rs_ext: float
    Sg_ext: float = 0.0


# ── История расчёта ──────────────────────────────────────────

@dataclass
class SimulationHistory:
    """Контейнер результатов расчёта — сохранённые шаги."""
    times: list[float] = field(default_factory=list)
    states: list[SimulationState] = field(default_factory=list)
    hydro_results: list[HydroResult] = field(default_factory=list)
    well_data: list[WellData] = field(default_factory=list)

    def append(self, t: float, state: SimulationState,
               hydro: HydroResult, well: WellData) -> None:
        self.times.append(t)
        self.states.append(state)
        self.hydro_results.append(hydro)
        self.well_data.append(well)

    @property
    def n_saved(self) -> int:
        return len(self.times)
