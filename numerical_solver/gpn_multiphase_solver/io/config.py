"""Чтение JSON-конфига и валидация. Все единицы — SI.

Структура JSON: см. P8-формат-ввода-json.md.
Секции: geometry, grid, rock, pvt, relperm, thermal, initial_conditions, time, numerics, output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
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
    mu_o_undersaturated: str = "none"  # μ_o при p > pb: "none" | "beal" (FEAT-027)
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
    # Дебит НЕФТИ в стандартных условиях, м³ст/с (control='rate', FEAT-020).
    # Именно нефти, не суммарный расход: прототип выражает p_bhp из
    # уравнения притока нефти (blackoil.py, _well_fluxes: в знаменателе одна λ_o),
    # а свободный газ досчитывается по тому же перепаду и не управляется.
    # Прежнее имя q_total обещало суммарный расход, которого нет.
    # Единицы СИ, как у остальных полей; конверсию в м³ст/сут,
    # ожидаемые прототипом, делает адаптер — там же, где Па → бар.
    q_oil: Optional[float] = None
    min_bhp: Optional[float] = None  # минимальное забойное давление, Па (обязательно при control='rate')


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
    # Глубина дробления шага (Simulator, локальное дробление DEBT-015):
    # подшаг, на котором Newton не сошёлся, делится пополам, наименьший
    # подшаг — time.dt_integration / 2**max_retries. Значение 9 (dt/512) —
    # запас, а не порог. Порогом оно было до BUG-014 (пример 03, N = 75,
    # p_wf = 6 МПа) и до BUG-016 (пример 04a, N = 80, высокая Sg — BUG-003);
    # после них оба сценария проходят без дробления. Таблицы README примеров
    # 03 и 04 дают не больше 5 удвоений (замер DEBT-041, повторён DEBT-015 —
    # те же числа). Лимит читается только при отказе, сходящийся расчёт он
    # не замедляет.
    max_retries: int = 9


# ── Секция output ────────────────────────────────────────────

@dataclass
class OutputConfig:
    """Параметры вывода."""
    log_level: str = "INFO"
    format: str = "npz"       # формат записи: "npz" или "csv"
    # save_every удалён (DEBT-013): частоту вывода задаёт структура
    # time.history — второго механизма отбора записей больше нет.


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
    config_dir: Path = field(default_factory=lambda: Path("."))


# ── Краткие формы time.history (FEAT-018) ────────────────────

# Ключи объекта истории, задающие время. Остальные ключи — управление
# скважиной (control, p_wf, q_oil, min_bhp); они передаются
# в HistoryInterval без изменений.
_HISTORY_TIME_KEYS = frozenset({"dt", "repeat", "duration", "dt_out"})

# Допустимые наборы ключей времени:
#   {dt}               — один интервал (исходная форма, DEBT-013);
#   {dt, repeat}       — repeat одинаковых интервалов по dt;
#   {duration, dt_out} — этап duration с записью раз в dt_out.
_HISTORY_FORMS = (
    frozenset({"dt"}),
    frozenset({"dt", "repeat"}),
    frozenset({"duration", "dt_out"}),
)

# Допуск кратности duration / dt_out. Поглощает только двоичное
# округление десятичной записи (0.3 / 0.1 = 2.9999999999999996);
# настоящая некратность отличается на долю шага — на много порядков больше.
_MULTIPLE_RTOL = 1e-9


def _expand_history(raw_history: list[dict]) -> list[HistoryInterval]:
    """Развернуть краткие формы time.history в список интервалов (FEAT-018)."""
    intervals: list[HistoryInterval] = []
    for i, raw_entry in enumerate(raw_history):
        where = f"history[{i}]"
        entry = dict(raw_entry)          # копия: не портим исходный словарь
        form = frozenset(entry) & _HISTORY_TIME_KEYS
        if form not in _HISTORY_FORMS:
            given = ", ".join(sorted(form)) or "нет ни dt, ни duration"
            raise ValueError(
                f"{where}: неверный набор полей времени ({given}); "
                f"допустимы dt, dt + repeat или duration + dt_out")

        if "duration" in form:
            # Этап duration с записью раз в dt_out → n интервалов по dt_out.
            # Длина интервала — ровно dt_out: моменты записи t0 + k·dt_out.
            duration = entry.pop("duration")
            dt = entry.pop("dt_out")
            if duration <= 0:
                raise ValueError(
                    f"{where}.duration должна быть > 0, получено {duration}")
            if dt <= 0:
                raise ValueError(
                    f"{where}.dt_out должен быть > 0, получено {dt}")
            n = round(duration / dt)
            # Некратность — ошибка, а не укороченный последний интервал:
            # иначе последний шаг записи молча отличался бы от заданного
            # (решение пользователя, FEAT-018). n < 1 — dt_out длиннее этапа.
            if n < 1 or abs(n * dt - duration) > _MULTIPLE_RTOL * duration:
                raise ValueError(
                    f"{where}: duration = {duration} с не кратна "
                    f"dt_out = {dt} с (отношение {duration / dt:.6g}); "
                    f"задайте кратные значения или разбейте этап на блоки")
        else:
            dt = entry.pop("dt")
            n = entry.pop("repeat", 1)
            # repeat идёт в range(): bool исключается явно (подкласс int),
            # дробное отвергается — как у numerics.max_retries.
            if isinstance(n, bool) or not isinstance(n, int) or n < 1:
                raise ValueError(
                    f"{where}.repeat должен быть целым >= 1, получено {n!r}")

        proto = HistoryInterval(dt=dt, **entry)
        # Проверка один раз на объект JSON: развёрнутые интервалы равны
        # прототипу по всем полям. Номер в сообщении — номер объекта
        # в JSON, то есть место, которое пользователь правит.
        _validate_interval(proto, where)
        # replace() — отдельный объект на каждый интервал: общий объект
        # в n позициях списка менял бы весь блок при правке одного
        # интервала (тесты правят history[k] после загрузки).
        intervals.extend(replace(proto) for _ in range(n))
    return intervals


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
    # Краткие формы {dt, repeat} и {duration, dt_out} разворачиваются
    # здесь же (FEAT-018); решатель видит только явные интервалы.
    time_raw = raw["time"]
    history = _expand_history(time_raw.pop("history"))
    time_cfg = TimeConfig(history=history, **time_raw)

    # ── Опциональные секции ──
    numerics = NumericsConfig(**raw["numerics"]) if "numerics" in raw else NumericsConfig()
    # save_every удалён (DEBT-013): частоту вывода задаёт структура
    # time.history, а не счётчик подшагов. Старые конфиги отвергаем
    # с объяснением — молча проглотить нельзя, состав вывода изменится.
    # Проверка стоит ДО OutputConfig(**out_raw): иначе строгая распаковка
    # dataclass упадёт раньше с невнятным TypeError про лишний аргумент.
    if "output" in raw:
        out_raw = dict(raw["output"])          # копия: не портим исходный словарь
        if "save_every" in out_raw:
            raise ValueError(
                "output.save_every удалён (DEBT-013): частота записи "
                "результатов задаётся структурой time.history. Чтобы "
                "получить N моментов вывода, задайте N интервалов истории "
                "(кратко: {\"dt\": ..., \"repeat\": N} или "
                "{\"duration\": ..., \"dt_out\": ...}); "
                "dt_integration отвечает только за точность схемы.")
        output = OutputConfig(**out_raw)
    else:
        output = OutputConfig()

    config = SimulationConfig(
        geometry=geometry, grid=grid, rock=rock, pvt=pvt,
        relperm=relperm, thermal=thermal, initial_conditions=initial,
        time=time_cfg, numerics=numerics, output=output,
        config_dir=path.parent,
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

    # Интервалы проверены при разворачивании (_expand_history, FEAT-018):
    # только там известен номер объекта в JSON — после разворачивания
    # блока он теряется, и сообщение указало бы не на место правки.

    # max_retries — глубина дробления шага (наименьший подшаг dt/2**max_retries, DEBT-015).
    # bool исключается явно: в Python bool — подкласс int, а True как лимит бессмыслен.
    mr = cfg.numerics.max_retries
    if isinstance(mr, bool) or not isinstance(mr, int):
        raise ValueError(f"numerics.max_retries должен быть целым, получено {mr!r}")
    if mr < 0 or mr > 20:
        raise ValueError(
            f"numerics.max_retries должен быть в [0, 20], получено {mr}. "
            f"Верхняя граница защищает от опечатки: дробление до dt/2**20 бессмысленно.")


def _validate_interval(h: HistoryInterval, where: str) -> None:
    """Проверка одного интервала истории; where — его место в JSON."""
    if h.dt <= 0:
        raise ValueError(f"{where}.dt должен быть > 0, получено {h.dt}")
    if h.control == "pressure":
        if h.p_wf is None:
            raise ValueError(f"{where}: control='pressure', но p_wf не задано")
        if h.p_wf <= 0:
            raise ValueError(f"{where}.p_wf должно быть > 0, получено {h.p_wf}")
        # Мёртвые поля (DEBT-008): при управлении по давлению не читаются
        for name in ("q_oil", "min_bhp"):
            if getattr(h, name) is not None:
                raise ValueError(
                    f"{where}: control='pressure' не использует {name} — "
                    f"уберите поле или задайте control='rate'")
    elif h.control == "rate":
        # Дебит нефти при ст. условиях, м³ст/с; нагнетание не поддержано
        if h.q_oil is None:
            raise ValueError(f"{where}: control='rate', но q_oil не задан")
        if h.q_oil < 0:
            raise ValueError(f"{where}.q_oil должен быть >= 0, получено {h.q_oil}")
        # min_bhp обязателен: без него p_wf при λ_o -> 0 уходит в -inf
        if h.min_bhp is None:
            raise ValueError(f"{where}: control='rate', но min_bhp не задано")
        if h.min_bhp <= 0:
            raise ValueError(f"{where}.min_bhp должно быть > 0, получено {h.min_bhp}")
        if h.p_wf is not None:
            raise ValueError(
                f"{where}: control='rate' не использует p_wf — забойное "
                f"давление при заданном дебите вычисляется")
    else:
        raise ValueError(
            f"{where}.control = '{h.control}': допустимы 'pressure', 'rate'")
