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
    p: np.ndarray        # [N] давление в центрах ячеек, Па
    Sg: np.ndarray       # [N] газонасыщенность (So = 1 - Sg)
    Rs: np.ndarray       # [N] газосодержание, м³ст/м³ст
    T: np.ndarray        # [N] температура, К
    regime: np.ndarray   # [N] int: 1 = двухфазная (Sg свободна, Rs=Rs_eq),
                         #          2 = однофазная (Rs свободна, Sg=0)
    t: float             # текущее время, с


# ── Результат гидродинамического шага ────────────────────────

@dataclass
class HydroResult:
    """Потоки через грани после гидро-шага.

    Все массивы [N+1]: по одному значению на каждую грань (включая забой и контур).
    Конвенция знаков: >0 = от скважины (рост r). При типичном потоке все < 0.
    См. конвенции-знаков.md, словарь-код-физика.md §3.
    """
    state: SimulationState          # обновлённое состояние (p, Sg, Rs, regime)

    # Покомпонентные объёмные потоки при ст. условиях
    G_o: np.ndarray                 # [N+1] нефтяной компонент, м³ст/с (eq. 8)
    G_g: np.ndarray                 # [N+1] полный газовый компонент (растворённый + свободный), м³ст/с (eq. 9)
    G_free_gas: np.ndarray          # [N+1] только свободный газ, м³ст/с

    # Фазовые объёмные расходы при пл. условиях (без 1/Bo, 1/Bg)
    Q_o: np.ndarray                 # [N+1] нефтяная фаза, м³пл/с (eq. 24)
    Q_g: np.ndarray                 # [N+1] газовая фаза, м³пл/с (eq. 24)

    # Скорости фильтрации (Дарси) на гранях
    u_o: np.ndarray                 # [N+1] м/с; u_o = Q_o / (2πhr)
    u_g: np.ndarray                 # [N+1] м/с; u_g = Q_g / (2πhr)

    # Фазовые массовые расходы через грани
    m_o: np.ndarray                 # [N+1] кг/с; m_o = ρ_o_up · Q_o
    m_g: np.ndarray                 # [N+1] кг/с; m_g = ρ_g_up · Q_g

    # Покомпонентные массовые расходы через грани
    Gm_o: np.ndarray                # [N+1] кг/с; Gm_o = ρ_o_ст · G_o
    Gm_g: np.ndarray                # [N+1] кг/с; Gm_g = ρ_g_ст · G_g


# ── Результат теплового шага ─────────────────────────────────

@dataclass
class EnergyResult:
    """Температура после теплового шага."""
    T_new: np.ndarray


# ── Скважинные данные ────────────────────────────────────────

@dataclass
class WellData:
    """Скважинные параметры на одном сохранённом шаге.

    Дебиты > 0 при добыче (q = -G[0], знак инвертирован).
    """
    q_o_std: float     # дебит нефти, м³ст/с; q_o_std = -G_o[0]
    q_g_std: float     # дебит газа, м³ст/с; q_g_std = -G_g[0]
    m_o_well: float    # массовый дебит нефти, кг/с; = ρ_o_ст · q_o_std
    m_g_well: float    # массовый дебит газа, кг/с; = ρ_g_ст · q_g_std
    p_wf: float        # забойное давление, Па
    T_wf: float        # забойная температура, К


# ── Граничные условия ────────────────────────────────────────

@dataclass
class BoundaryConditions:
    """Полный набор граничных условий на текущем шаге.

    well — стратегия управления скважиной (забой, f=0).
    p_ext, T_ext, Rs_ext, Sg_ext — условия на контуре питания (f=N, Дирихле).
    """
    well: WellControl       # ABC: PressureControl, TotalRateControl, ...
    p_ext: float            # давление на контуре, Па
    T_ext: float            # температура на контуре, К
    Rs_ext: float           # газосодержание притока, м³ст/м³ст
    Sg_ext: float = 0.0     # газонасыщенность на контуре (обычно 0)


# ── История расчёта ──────────────────────────────────────────

# Ключи снимка баланса энергии. Дублируют CUMULATIVE_KEYS из
# energy/balance.py намеренно: импортировать оттуда нельзя — balance.py
# сам импортирует state.py, получился бы цикл. Список короткий
# и менялся бы только вместе с уравнением энергии.
_BALANCE_KEYS = ("delta_E", "cum_adiab", "cum_conv",
                 "cum_jt", "cum_deg", "cum_cond")


def _zero_balance() -> dict:
    """Нулевой снимок баланса — для начального состояния (DEBT-013)."""
    return {k: 0.0 for k in _BALANCE_KEYS}


@dataclass
class SimulationHistory:
    """Контейнер результатов расчёта — сохранённые шаги.

    Simulator.run() наполняет через append(), возвращает целиком.
    I/O-модуль принимает для записи CSV/NPZ и визуализации.
    Записи делаются на концах интервалов time.history — частоту вывода
    задаёт только расписание (DEBT-013).

    balance — накопленные члены баланса энергии на момент каждой записи
    (снимок EnergyBalanceAccumulator, словарь скаляров). Считается
    по ВСЕМ подшагам, а не по сохранённым состояниям, поэтому корректен
    при любой структуре истории, включая неравномерную (DEBT-013).
    """
    times: list[float] = field(default_factory=list)
    states: list[SimulationState] = field(default_factory=list)
    hydro_results: list[HydroResult] = field(default_factory=list)
    well_data: list[WellData] = field(default_factory=list)
    balance: list[dict] = field(default_factory=list)

    def append(self, t: float, state: SimulationState,
               hydro: HydroResult, well: WellData,
               balance: dict | None = None) -> None:
        """Добавить один сохранённый шаг."""
        self.times.append(t)
        self.states.append(state)
        self.hydro_results.append(hydro)
        self.well_data.append(well)
        # None → нулевой снимок: на начальном состоянии накоплений ещё нет.
        self.balance.append(balance if balance is not None
                            else _zero_balance())

    @property
    def n_saved(self) -> int:
        """Число сохранённых шагов."""
        return len(self.times)
