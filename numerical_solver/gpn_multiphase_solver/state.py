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
    """Состояние пласта в момент времени t: значения в центрах ячеек, индекс 0 — ячейка у забоя.

    Атрибуты
    --------
    p : numpy.ndarray
        Давление, Па; длина N.
    Sg : numpy.ndarray
        Газонасыщенность, доли; нефтенасыщенность S_o = 1 − S_g.
    Rs : numpy.ndarray
        Газосодержание нефти, м³ст/м³ст.
    T : numpy.ndarray
        Температура, К.
    regime : numpy.ndarray
        Фазовый режим ячейки (целые): 1 — двухфазная (газосодержание
        равновесное), 2 — однофазная (свободного газа нет).
    t : float
        Время, с.
    """
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
    G_o: np.ndarray                 # [N+1] нефтяной компонент, м³ст/с (eq:flux_oil)
    G_g: np.ndarray                 # [N+1] полный газовый компонент (растворённый + свободный), м³ст/с (eq:flux_gas)
    G_free_gas: np.ndarray          # [N+1] только свободный газ, м³ст/с

    # Фазовые объёмные расходы при пл. условиях (без 1/Bo, 1/Bg)
    Q_o: np.ndarray                 # [N+1] нефтяная фаза, м³пл/с (eq:phase_flux)
    Q_g: np.ndarray                 # [N+1] газовая фаза, м³пл/с (eq:phase_flux)

    # Скорости фильтрации (Дарси) на гранях
    u_o: np.ndarray                 # [N+1] м/с; u_o = Q_o / (2πhr)
    u_g: np.ndarray                 # [N+1] м/с; u_g = Q_g / (2πhr)

    # Фазовые массовые расходы через грани
    m_o: np.ndarray                 # [N+1] кг/с; m_o = ρ_o_up · Q_o
    m_g: np.ndarray                 # [N+1] кг/с; m_g = ρ_g_up · Q_g

    # Покомпонентные массовые расходы через грани
    Gm_o: np.ndarray                # [N+1] кг/с; Gm_o = ρ_o_ст · G_o
    Gm_g: np.ndarray                # [N+1] кг/с; Gm_g = ρ_g_ст · G_g

    # Фактическое давление на забойной грани после шага, Па. Результат
    # гидродинамики при любом управлении: при заданном дебите выражается
    # из уравнения притока (eq:bc_rate_pwf), при закрытой скважине равно
    # p[0]. Энергия и вывод берут p_wf только отсюда — единый источник
    # гидродинамических величин (FEAT-020). Без умолчания: запасной путь
    # через bc.well вернул бы второй источник.
    p_wf: float

    # Интегралы потоков компонентов через забой и контур за шаг решателя, м³ст
    # (DEBT-039): ∫G[0] dt и ∫G[N] dt. Знак — как у G (> 0 от скважины): при
    # добыче int_G_*_well < 0, при притоке с контура int_G_*_ext < 0. Нужны
    # балансу массы: решатель с внутренними подшагами отдаёт G последнего из
    # них, и dt·G от интеграла отличается (замер DEBT-039: невязка шага
    # 9·10⁻² вместо ≤ 10⁻¹⁰). PrototypeHydroAdapter подшагов не делает
    # (DEBT-015) — у него интеграл равен dt·G. None — решатель массу не
    # сохраняет (тестовые двойники); тогда и его component_inventories — None.
    int_G_o_well: float | None = None
    int_G_o_ext: float | None = None
    int_G_g_well: float | None = None
    int_G_g_ext: float | None = None


# ── Результат теплового шага ─────────────────────────────────

@dataclass
class EnergyResult:
    """Температура после теплового шага."""
    T_new: np.ndarray


# ── Скважинные данные ────────────────────────────────────────

# Дебиты > 0 при добыче: q = −G[0], знак потока на забойной грани
# инвертирован (конвенция знаков — от скважины)
@dataclass
class WellData:
    """Данные скважины на одной записи истории; дебиты при добыче положительны.

    Атрибуты
    --------
    q_o_std : float
        Дебит нефти в стандартных условиях, м³ст/с.
    q_g_std : float
        Дебит газа (растворённого и свободного) в стандартных условиях, м³ст/с.
    m_o_well : float
        Массовый дебит нефтяного компонента, кг/с.
    m_g_well : float
        Массовый дебит газового компонента, кг/с.
    p_wf : float
        Забойное давление, Па.
    T_wf : float
        Забойная температура, К, — температура в центре ячейки 0 (``T[0]``).
        При скине больше нуля не содержит дросселирования на перепаде
        скин-зоны: скин учитывается только в гидродинамике.
    """
    q_o_std: float     # дебит нефти, м³ст/с; q_o_std = -G_o[0]
    q_g_std: float     # дебит газа, м³ст/с; q_g_std = -G_g[0]
    m_o_well: float    # массовый дебит нефти, кг/с; = ρ_o_ст · q_o_std
    m_g_well: float    # массовый дебит газа, кг/с; = ρ_g_ст · q_g_std
    p_wf: float        # забойное давление, Па
    # При скине s > 0 T_wf не содержит дросселирования и разгазирования на
    # перепаде скин-зоны: скин входит только в гидродинамику (BUG-029)
    T_wf: float        # забойная температура, К: T[0] — центр r_0 ячейки 0 (BUG-015)


# ── Граничные условия ────────────────────────────────────────

# well — забойная грань f = 0; p_ext, T_ext, Rs_ext, Sg_ext — контур питания,
# грань f = N, условия Дирихле
@dataclass
class BoundaryConditions:
    """Граничные условия на интервале истории: режим скважины на забое и значения на контуре питания.

    Атрибуты
    --------
    well : WellControl
        Режим работы скважины: ``PressureControl`` или ``RateControl``.
    p_ext : float
        Давление на контуре питания, Па.
    T_ext : float
        Температура на контуре питания, К.
    Rs_ext : float
        Газосодержание притекающей нефти, м³ст/м³ст.
    Sg_ext : float
        Газонасыщенность на контуре, доли; умолчание 0 (приток однофазный).
    """
    well: WellControl       # PressureControl или RateControl (bc.py)
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


# Simulator.run наполняет историю через append. Записи — на концах интервалов
# time.history: частоту вывода задаёт только расписание (DEBT-013). Члены
# баланса энергии (снимок EnergyBalanceAccumulator) и баланса массы (снимок
# MassBalanceAccumulator, DEBT-039) копятся по ВСЕМ подшагам, а не по
# сохранённым состояниям, — корректны при любой структуре истории. None в
# mass_balance — решатель массу не сохраняет (тестовые двойники)
@dataclass
class SimulationHistory:
    """История расчёта: записи на концах интервалов режима скважины; первая — начальное состояние.

    Атрибуты
    --------
    times : list of float
        Моменты записей, с.
    states : list of SimulationState
        Состояние пласта на каждой записи.
    hydro_results : list of HydroResult
        Результат шага гидродинамики на каждой записи: потоки компонентов и
        фаз через грани ячеек (положительное направление — от скважины).
    well_data : list of WellData
        Данные скважины на каждой записи.
    balance : list of dict
        Члены баланса энергии, накопленные от начала расчёта, Дж: ключи
        ``delta_E``, ``cum_adiab``, ``cum_conv``, ``cum_jt``, ``cum_deg``,
        ``cum_cond``; ряды и невязку даёт :func:`compute_energy_balance`.
    mass_balance : list of dict or None
        Запасы компонентов и накопленные потоки через забой и контур, м³ст;
        ряды и невязку даёт :func:`compute_mass_balance`. ``None`` —
        решатель запас компонентов не ведёт.
    """
    times: list[float] = field(default_factory=list)
    states: list[SimulationState] = field(default_factory=list)
    hydro_results: list[HydroResult] = field(default_factory=list)
    well_data: list[WellData] = field(default_factory=list)
    balance: list[dict] = field(default_factory=list)
    mass_balance: list[dict | None] = field(default_factory=list)

    def append(self, t: float, state: SimulationState,
               hydro: HydroResult, well: WellData,
               balance: dict | None = None,
               mass_balance: dict | None = None) -> None:
        """Добавить один сохранённый шаг."""
        self.times.append(t)
        self.states.append(state)
        self.hydro_results.append(hydro)
        self.well_data.append(well)
        # None → нулевой снимок: на начальном состоянии накоплений ещё нет.
        self.balance.append(balance if balance is not None
                            else _zero_balance())
        # None — баланс массы не считается: решатель-двойник массу не
        # сохраняет (DEBT-039). Нулевого снимка, как у баланса энергии, нет:
        # запас компонентов в начальном состоянии не нулевой, его даёт решатель.
        self.mass_balance.append(mass_balance)

    @property
    def n_saved(self) -> int:
        """Число сохранённых шагов."""
        return len(self.times)
