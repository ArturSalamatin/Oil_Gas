"""Чтение JSON-конфига и валидация. Все единицы — SI.

Структура JSON: см. P8-формат-ввода-json.md.
Секции: geometry, grid, rock, pvt, relperm, thermal, initial_conditions, time, numerics, output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Секция geometry ──────────────────────────────────────────

@dataclass
class GeometryConfig:
    """Геометрия скважины и пласта."""
    r_well: float    # радиус скважины, м
    R_ext: float     # радиус контура питания, м
    h: float         # мощность пласта, м


# ── Секция grid ──────────────────────────────────────────────

@dataclass
class GridConfig:
    """Параметры сетки."""
    N: int                       # число ячеек
    type: str = "log_radial"     # тип сетки (пока только log_radial)


# ── Секция rock ──────────────────────────────────────────────

@dataclass
class RockConfig:
    """Свойства породы."""
    porosity: float          # φ, безразмерная
    permeability: float      # k, м²
    # Тепловые свойства породы
    rho_cp_solid: float = 1.25e6    # (ρc_p)_s, Дж/(м³·К)
    lambda_solid: float = 1.5       # λ_s, Вт/(м·К)
    lambda_oil: float = 0.14        # λ_o (фазы), Вт/(м·К)
    lambda_gas: float = 0.04        # λ_g (фазы), Вт/(м·К)
    # Компрессия породы (пока не используется)
    p_ref: float = 1e7              # опорное давление, Па
    compressibility: float = 0.0    # c_r, 1/Па


# ── Секция pvt ───────────────────────────────────────────────

@dataclass
class PVTConfig:
    """Параметры PVT-модели."""
    model: str              # "standing" или "table"
    rho_o_std: float        # плотность нефти при ст. условиях, кг/м³
    rho_g_std: float        # плотность газа при ст. условиях, кг/м³
    # Для Standing
    co_undersaturated: float = 0.0   # сжимаемость нефти при p > pb, 1/Па
    # Для табличного PVT — имена CSV-файлов (относительно JSON)
    oil_pvt_file: Optional[str] = None
    gas_pvt_file: Optional[str] = None


# ── Секция relperm ───────────────────────────────────────────

@dataclass
class RelPermConfig:
    """Параметры модели ОФП."""
    model: str          # "corey" или "table"
    # Для Corey
    S_or: float = 0.2
    S_gc: float = 0.05
    n_o: float = 2.0
    n_g: float = 2.0
    kro_max: float = 1.0
    krg_max: float = 0.8
    # Для табличного ОФП
    file: Optional[str] = None


# ── Секция thermal ───────────────────────────────────────────

@dataclass
class ThermalConfig:
    """Скалярные тепловые свойства флюида."""
    c_p_oil: float = 2000.0          # Дж/(кг·К)
    c_p_gas: float = 1000.0          # Дж/(кг·К)
    mu_JT_oil: float = 0.0           # К/Па
    mu_JT_gas: float = 0.0           # К/Па
    L_degas: float = 0.0             # Дж/кг газа


# ── Секция initial_conditions ────────────────────────────────

@dataclass
class InitialConfig:
    """Начальные условия (однородные по пласту)."""
    p0: float        # начальное давление, Па
    T0: float        # начальная температура, К
    Rs0: float       # начальное газосодержание, м³ст/м³ст


# ── Секция time ──────────────────────────────────────────────

@dataclass
class HistoryInterval:
    """Один интервал истории."""
    dt: float                        # длительность, с
    control: str = "pressure"        # тип управления: "pressure" или "rate"
    p_wf: Optional[float] = None     # забойное давление, Па (для pressure)
    q_total: Optional[float] = None  # расход, м³ст/с (для rate, будущее)
    min_bhp: Optional[float] = None  # минимальное забойное давление, Па (для rate)


@dataclass
class TimeConfig:
    """Временна́я сетка и история."""
    dt_integration: float                  # шаг интегрирования, с
    history: list[HistoryInterval]         # список интервалов
    start_day: float = 0.0                 # начало истории, сут


# ── Секция numerics ──────────────────────────────────────────

@dataclass
class NumericsConfig:
    """Параметры численного метода (передаются в Newton-солвер прототипа)."""
    dt_min: float = 1.0                    # минимальный шаг, с
    dt_max: float = 86400.0                # максимальный шаг, с
    skin: float = 0.0                      # скин-фактор
    newton_max_iter: int = 15
    newton_rtol: float = 1e-8
    newton_atol: float = 1e-11
    max_active_set_iter: int = 12
    rs_switch_tol: float = 1e-5
    sg_switch_tol: float = 1e-9
    jacobian_mode: str = "grouped"
    linear_solver: str = "sparse"


# ── Секция output ────────────────────────────────────────────

@dataclass
class OutputConfig:
    """Параметры вывода."""
    log_level: str = "INFO"
    format: str = "npz"       # формат записи: "npz" или "csv"
    save_every: int = 1       # сохранять каждый N-й шаг


# ── Полный конфиг ────────────────────────────────────────────

@dataclass
class SimulationConfig:
    """Полная конфигурация расчёта."""
    geometry: GeometryConfig
    grid: GridConfig
    rock: RockConfig
    pvt: PVTConfig
    relperm: RelPermConfig
    thermal: ThermalConfig
    initial_conditions: InitialConfig
    time: TimeConfig
    numerics: NumericsConfig = field(default_factory=NumericsConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


# ── Загрузка ─────────────────────────────────────────────────

def load_config(path: str | Path) -> SimulationConfig:
    """Прочитать JSON-конфиг и вернуть SimulationConfig.

    Валидирует обязательные секции и физические ограничения.
    Путь к CSV-файлам PVT — относительно расположения JSON.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    # ── Обязательные секции ──
    for key in ("geometry", "grid", "rock", "pvt", "relperm",
                "thermal", "initial_conditions", "time"):
        if key not in raw:
            raise ValueError(f"Отсутствует обязательная секция '{key}' в {path}")

    geometry = GeometryConfig(**raw["geometry"])
    grid = GridConfig(**raw["grid"])
    rock = RockConfig(**raw["rock"])
    pvt = PVTConfig(**raw["pvt"])
    relperm = RelPermConfig(**raw["relperm"])
    thermal = ThermalConfig(**raw["thermal"])
    initial = InitialConfig(**raw["initial_conditions"])

    # ── time: history — список словарей → список HistoryInterval ──
    time_raw = raw["time"]
    history = [HistoryInterval(**h) for h in time_raw.pop("history")]
    time_cfg = TimeConfig(history=history, **time_raw)

    # ── Опциональные секции ──
    numerics = NumericsConfig(**raw["numerics"]) if "numerics" in raw else NumericsConfig()
    output = OutputConfig(**raw["output"]) if "output" in raw else OutputConfig()

    config = SimulationConfig(
        geometry=geometry, grid=grid, rock=rock, pvt=pvt,
        relperm=relperm, thermal=thermal, initial_conditions=initial,
        time=time_cfg, numerics=numerics, output=output,
    )

    _validate(config)
    return config


def _validate(cfg: SimulationConfig) -> None:
    """Физическая валидация параметров."""
    g = cfg.geometry
    if g.r_well <= 0:
        raise ValueError(f"r_well должен быть > 0, получено {g.r_well}")
    if g.R_ext <= g.r_well:
        raise ValueError(f"R_ext ({g.R_ext}) должен быть > r_well ({g.r_well})")
    if g.h <= 0:
        raise ValueError(f"h должен быть > 0, получено {g.h}")

    if cfg.grid.N < 1:
        raise ValueError(f"N должен быть ≥ 1, получено {cfg.grid.N}")

    r = cfg.rock
    if r.porosity <= 0 or r.porosity > 1:
        raise ValueError(f"porosity должна быть в (0, 1], получено {r.porosity}")
    if r.permeability <= 0:
        raise ValueError(f"permeability должна быть > 0, получено {r.permeability}")

    ic = cfg.initial_conditions
    if ic.p0 <= 0:
        raise ValueError(f"p0 должно быть > 0, получено {ic.p0}")
    if ic.T0 <= 0:
        raise ValueError(f"T0 должна быть > 0, получено {ic.T0}")
    if ic.Rs0 < 0:
        raise ValueError(f"Rs0 должно быть ≥ 0, получено {ic.Rs0}")

    if cfg.time.dt_integration <= 0:
        raise ValueError(f"dt_integration должен быть > 0, получено {cfg.time.dt_integration}")
    if len(cfg.time.history) == 0:
        raise ValueError("history должна содержать хотя бы один интервал")

    for i, h in enumerate(cfg.time.history):
        if h.dt <= 0:
            raise ValueError(f"history[{i}].dt должен быть > 0, получено {h.dt}")
        if h.control == "pressure" and h.p_wf is None:
            raise ValueError(f"history[{i}]: control='pressure', но p_wf не задано")
        if h.control == "pressure" and h.p_wf is not None and h.p_wf <= 0:
            raise ValueError(f"history[{i}].p_wf должно быть > 0, получено {h.p_wf}")
