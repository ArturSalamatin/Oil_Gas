"""Чтение JSON-конфига и валидация. Все единицы — SI.

Структура JSON: см. P8-формат-ввода-json.md.
Секции: geometry, grid, rock, pvt, relperm, thermal, initial_conditions, time, numerics, output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Optional

import numpy as np

from ..log import user_log


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
    """Параметры численного метода; часть полей никто не читает (DEBT-008)."""
    # Читаются: skin, jacobian_mode, linear_solver, newton_cell_tol — фабрика (прототипу),
    # max_retries — Simulator. Не читаются: dt_min, dt_max; newton_max_iter, newton_rtol,
    # newton_atol, max_active_set_iter, rs_switch_tol, sg_switch_tol (прототип — свои умолчания).
    dt_min: float = 1.0                    # минимальный шаг, с
    dt_max: float = 86400.0                # максимальный шаг, с
    skin: float = 0.0                      # скин-фактор: ≥ 0, > 50 — предупреждение (DEBT-056)
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
    # Условие сходимости Ньютона по ячейке (BUG-022), безразмерное: решение принимается,
    # только если кроме абсолютного критерия прототипа ||F||_inf <= atol + rtol·||F_0||_inf
    # в каждой ячейке max_c |F_c,i|·Δt / V_p,i <= newton_cell_tol (F — невязка компонента,
    # м³ст/с, газ поделён на max(R_s,ext, 1); V_p — поровый объём на начало шага, м³).
    # Абсолютный критерий один на все ячейки, а поровый объём забойной ячейки в
    # ~(R_ext/r_w)^2 раз меньше, чем у внешней: без условия R_s у забоя примера 17 на
    # останове блуждал на ±0.015 за сутки. Для недонасыщенной ячейки, которая ни на одной
    # грани не стоит выше по потоку (забойная на останове), оценка ошибки R_s за шаг —
    # newton_cell_tol·B_o·(max(R_s,ext, 1) + R_s): у забоя 17 — 4.6e-6. 1e-8 — замер
    # BUG-022: 1e-7 мало (убывание R_s до 2.9e-4), 1e-9 дороже на 8 % якобианов.
    # Порог на порядок ниже ~2.2e-16·(R_ext/r_w)^2 не выполняется, шаги дробятся: при
    # 1e-10 у 17 отказов шагов 214 против 47, якобианов ×2.9 (оценка для 17 — 8e-10;
    # при R_ext/r_w = 1e4 и 1e-8 — вдвое ниже оценки — лишь +8 отказов из 38). null — выкл.
    # Передаётся прототипу (cell_tol), в отличие от newton_atol и newton_rtol (DEBT-008).
    newton_cell_tol: Optional[float] = 1e-8


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


def _expand_history(raw_history: list[dict]
                    ) -> tuple[list[HistoryInterval], list[tuple[str, HistoryInterval]]]:
    """Развернуть time.history (FEAT-018); второй результат — пары (место в JSON, образец)."""
    intervals: list[HistoryInterval] = []
    # Образец интервала на каждый объект JSON с его местом history[i]:
    # по ним _warn_well_shut предупреждает один раз на объект (DEBT-056)
    blocks: list[tuple[str, HistoryInterval]] = []
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
            # Число и конечность — до сравнений: NaN проходит `<= 0`, а
            # round(duration / dt) ниже падал на нём без имени поля (DEBT-051)
            _require_finite_number(duration, f"{where}.duration")
            _require_finite_number(dt, f"{where}.dt_out")
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
        blocks.append((where, proto))
        # replace() — отдельный объект на каждый интервал: общий объект
        # в n позициях списка менял бы весь блок при правке одного
        # интервала (тесты правят history[k] после загрузки).
        intervals.extend(replace(proto) for _ in range(n))
    return intervals, blocks


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
    history, history_blocks = _expand_history(time_raw.pop("history"))
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
    # Предупреждения — после всех проверок _validate: конфиг с ошибкой в любом
    # поле не выдаёт предупреждение перед отказом (DEBT-056)
    _warn_large_skin(config)
    # p0 к этому моменту проверен в _validate: число, конечное, > 0
    _warn_well_shut(history_blocks, config.initial_conditions.p0)
    return config


# Секции, числовые поля которых проверяет _check_numeric_fields (DEBT-051).
# Интервалы истории — в _validate_interval: там известен номер объекта JSON.
_NUMERIC_SECTIONS = ("geometry", "grid", "rock", "pvt", "relperm", "thermal",
                     "initial_conditions", "time", "numerics")

# Порог предупреждения о скине (решение пользователя, DEBT-056). У baseline
# (R_ext/r_w = 500) при s = 50 установившийся однофазный приток — 11 %
# от притока без скина при той же депрессии.
_SKIN_WARN = 50.0


def _require_finite_number(value, name: str) -> None:
    """Число (не строка, null, bool) и конечное, иначе ValueError с именем name (DEBT-051)."""
    # bool — подкласс int: true в числовом поле — опечатка, а не 1.0
    # (замер: permeability = true — 1 м², отказ после дробления до dt/512)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} должно быть числом, получено {value!r}")
    # Сравнение с NaN ложно: условие отсекает и NaN, и ±inf (литералы JSON
    # NaN, Infinity, -Infinity; 1e999 модуль json тоже читает как inf)
    if not (-float("inf") < value < float("inf")):
        raise ValueError(f"{name} должно быть конечным числом, получено {value}")


def _check_numeric_fields(obj, where: str) -> None:
    """Числовые поля dataclass-секции obj — через _require_finite_number (DEBT-051)."""
    # Аннотации — строки (from __future__ import annotations): «float»,
    # «Optional[float]». Поле с иначе записанной аннотацией выпадет из проверки
    # (страж — test_config.py::test_field_list_covers_known_fields). null
    # допустим только в Optional-поле. Значение float в поле другого типа
    # (NaN в grid.N) проверяется на конечность.
    for f in fields(obj):
        value = getattr(obj, f.name)
        typed = f.type == "float" or (f.type == "Optional[float]" and value is not None)
        if typed or isinstance(value, float):
            _require_finite_number(value, f"{where}.{f.name}")


def _validate(cfg: SimulationConfig) -> None:
    """Физическая валидация параметров."""
    # Число и конечность всех числовых полей — до проверок диапазона (DEBT-051).
    # Проверки вида `v <= 0` NaN пропускают: сравнение с NaN ложно. Замер до
    # DEBT-051 (vault/issues/debt-051/probes/red_state.out.txt, 24 ч при
    # p_wf = 6 МПа): NaN в p0, porosity и ещё 11 полях — отказ после дробления
    # первого шага до dt/512 с советом увеличить max_retries; skin = ±inf и
    # p_wf = +inf — расчёт без добычи; min_bhp = NaN — ограничение по забою
    # снято молча (забой 7.12 МПа при min_bhp = 15 МПа).
    for name in _NUMERIC_SECTIONS:
        _check_numeric_fields(getattr(cfg, name), name)

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

    # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──
    # Проводимость забойной грани прототипа (radial_blackoil/grid.py,
    # well_transmissibility_m3): T_w = 2πkh / (ln(r_1/r_w) + s), r_1 — центр
    # первой ячейки; ln(r_1/r_w) = ln(R_ext/r_w)/(2N), на сетках проекта
    # 0.01…0.16. Скин стимулированной скважины (s ≈ −0.5…−5) даёт T_w < 0;
    # замер до DEBT-056 (vault/issues/debt-056/probes/skin_range.out.txt):
    # s = −0.5 и −2 — отказ после дробления шага до dt/512 с советом увеличить
    # max_retries. Отрицательный скин в проекте не предусмотрен (решение
    # пользователя) — отказ при любом s < 0, сетка проверке не нужна. Обход —
    # приведённый радиус скважины r_w·e^(−s): при s = 0 установившийся
    # однофазный приток тот же, p − p_wf = qμ/(2πkh)·ln(r/(r_w·e^(−s))).
    s = cfg.numerics.skin
    if s < 0:
        # r_w·e^(−s) < R_ext сравнивается в логарифмах: при s = −1e300 (конечное,
        # проходит DEBT-051) np.exp(−s) переполняется с RuntimeWarning
        ln_re_rw = np.log(g.R_ext / g.r_well)
        if -s < ln_re_rw:
            r_eq = g.r_well * np.exp(-s)
            hint = (f"Обход: geometry.r_well = r_w·e^(−s) = {r_eq:.4g} м и "
                    f"numerics.skin = 0 (приведённый радиус скважины: тот же "
                    f"установившийся однофазный приток); температура забоя тогда "
                    f"относится к r = {r_eq:.4g} м, а не к r_w = {g.r_well} м.")
        else:
            hint = (f"Приведённый радиус r_w·e^(−s) не меньше R_ext = {g.R_ext} м "
                    f"(s ≤ −ln(R_ext/r_w) = {-ln_re_rw:.3g}) — обход через "
                    f"geometry.r_well неприменим.")
        raise ValueError(
            f"numerics.skin = {s} < 0: отрицательный скин (стимулированная "
            f"скважина) в проекте не предусмотрен — проводимость забойной грани "
            f"2πkh/(ln(r_1/r_w) + s) на сетках проекта неположительна уже при "
            f"s ≈ −0.01…−0.16. {hint}")

    # Тепловые параметры (DEBT-047, P8 §5). Ошибка в них не роняет расчёт,
    # а даёт правдоподобную, но неверную T. Замер до DEBT-047
    # (vault/issues/debt-047/probes/red_state.out.txt, baseline, 24 ч):
    # c_p,o = 0 при p_wf = 6 МПа — T_min = 11.8 К; (ρc_p)_s = 0 — 0.9 К
    # отклонения; λ < 0 — тысячные доли кельвина. NaN и inf сюда не доходят:
    # их отвергает _check_numeric_fields в начале функции (DEBT-051). Условие
    # `0 < v < inf` осталось от DEBT-047, где отсекало и их (иначе отказ дала
    # бы scipy в СЛАУ энергии без имени параметра).
    inf = float("inf")
    th = cfg.thermal
    for name, value in (("rock.rho_cp_solid", r.rho_cp_solid),
                        ("thermal.c_p_oil", th.c_p_oil),
                        ("thermal.c_p_gas", th.c_p_gas)):
        if not (0 < value < inf):
            raise ValueError(f"{name} должна быть конечной и > 0, получено {value}")
    # λ = 0 допустимо: так отключают теплопроводность (примеры 01–09, 04a)
    for name, value in (("rock.lambda_solid", r.lambda_solid),
                        ("rock.lambda_oil", r.lambda_oil),
                        ("rock.lambda_gas", r.lambda_gas)):
        if not (0 <= value < inf):
            raise ValueError(f"{name} должна быть конечной и ≥ 0, получено {value}")
    # L, μ_JT,o, μ_JT,g — знак любой (P8 §5): у жидкости μ_JT обычно < 0
    # (нагрев при дросселировании), у газа > 0; L < 0 возможна (см. ниже).
    # Конечность проверил _check_numeric_fields в начале функции (DEBT-051;
    # до него — отдельный цикл DEBT-049): раньше предупреждений о знаке, так
    # что при L = −inf в журнал не уходит предупреждение перед отказом.
    # L < 0 — предупреждение, не отказ (решение пользователя, DEBT-047).
    # Q_deg = −L·ṁ (energy/tridiag.py, compute_degassing): при L < 0
    # выделение газа нагревает пласт (замер: +3.2 К при p_wf = 6 МПа).
    # По Стендингу p_b растёт с T, то есть при заданном p R_s с ростом T
    # убывает: растворение газа экзотермично, дегазация поглощает теплоту,
    # L > 0. Для систем, где растворимость газа растёт с T, L < 0 физически
    # возможен (P8 §5), поэтому расчёт не запрещается.
    if th.L_degas < 0:
        user_log.warning(
            f"thermal.L_degas = {th.L_degas} Дж/кг < 0: выделение газа в расчёте "
            f"нагревает пласт (Q_deg = −L·ṁ > 0); при L > 0 дегазация охлаждает. "
            f"Проверьте знак.")
    # μ_JT,o > 0 — предупреждение, не отказ (решение пользователя, DEBT-049).
    # μ_JT = (∂T/∂p)_h = v(αT − 1)/c_p (problem_statement.tex, eq:muJT_def):
    # у нефти αT ≈ 0.3 (α ≈ 1e-3 1/К, T ≈ 350 К), μ_JT,o ≈ −4e-7 К/Па —
    # при дросселировании нефть греется. μ_JT,o > 0 требует αT > 1, для
    # нефти в пласте это нереально; вероятная причина — знак ε = −μ_JT из
    # литературы (Шарафутдинов и др., 2019), так было в конфигах примеров
    # до 2026-09-29. У газа μ_JT,g < 0 законен выше давления инверсии —
    # без предупреждения.
    if th.mu_JT_oil > 0:
        user_log.warning(
            f"thermal.mu_JT_oil = {th.mu_JT_oil} К/Па > 0: нефть при дросселировании "
            f"в расчёте охлаждается; у жидкости μ_JT = v(αT − 1)/c_p < 0 (нагрев). "
            f"Проверьте знак: в литературе встречается ε = −μ_JT.")

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

    # newton_cell_tol — порог условия сходимости по ячейке (BUG-022); None (null) —
    # выключено. Тип и конечность (bool, строка, NaN, ±inf) отверг _check_numeric_fields
    # в начале функции (DEBT-051): здесь — только знак.
    ct = cfg.numerics.newton_cell_tol
    if ct is not None and not 0.0 < ct:
        raise ValueError(
            f"numerics.newton_cell_tol должен быть положительным конечным числом или null, "
            f"получено {ct!r}")


def _validate_interval(h: HistoryInterval, where: str) -> None:
    """Проверка одного интервала истории; where — его место в JSON."""
    # Число и конечность dt, p_wf, q_oil, min_bhp — до сравнений (DEBT-051):
    # `h.min_bhp <= 0` NaN пропускал, и ограничение по забою снималось молча
    _check_numeric_fields(h, where)
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


def _warn_large_skin(cfg: SimulationConfig) -> None:
    """Предупреждение при скине выше _SKIN_WARN (DEBT-056)."""
    # s > 50 — предупреждение, не отказ (решение пользователя, DEBT-056).
    # Доля установившегося однофазного притока при той же депрессии:
    # q(s)/q(0) = ln(R_ext/r_w) / (ln(R_ext/r_w) + s); на сетке прототипа
    # сопротивления граней складываются ровно в ln(R_ext/r_w). Замер до
    # DEBT-056 (vault/issues/debt-056/probes/skin_range.out.txt): s = 1e3 —
    # минимум p 19.91 МПа при p0 = 20, s = 1e6 — притока нет, расчёт молча идёт.
    s = cfg.numerics.skin
    if s > _SKIN_WARN:
        g = cfg.geometry
        ln_re_rw = np.log(g.R_ext / g.r_well)
        ratio = ln_re_rw / (ln_re_rw + s)
        user_log.warning(
            f"numerics.skin = {s} > {_SKIN_WARN:g}: установившийся однофазный приток "
            f"при той же депрессии — {ratio:.1%} от притока без скина "
            f"(ln(R_ext/r_w) / (ln(R_ext/r_w) + s), ln(R_ext/r_w) = {ln_re_rw:.3g}). "
            f"Проверьте значение.")


def _warn_well_shut(blocks: list[tuple[str, HistoryInterval]], p0: float) -> None:
    """Объекты истории, где скважина заведомо закрыта (DEBT-056). Ур. (eq:bc_pwf_shutin)."""
    # Только добыча (FEAT-020): при p_wf ≥ p в ячейке забоя приток нулевой,
    # нагнетания нет. При добыче давление в пласте не выше p0 (контур питания
    # держит p0, источников нет), поэтому p_wf ≥ p0 закрывает скважину на весь
    # интервал; при control='rate' то же даёт min_bhp ≥ p0 — забой не может
    # опуститься ниже p0. Замер до DEBT-056 (vault/issues/debt-056/probes/
    # skin_range.out.txt): p_wf = 25 МПа и min_bhp = 25 МПа при p0 = 20 МПа —
    # расчёт без притока и без сообщения.
    for where, h in blocks:
        if h.control == "pressure" and h.p_wf >= p0:
            user_log.warning(
                f"{where}: p_wf = {h.p_wf:.6g} Па ≥ p0 = {p0:.6g} Па — давление "
                f"в пласте при добыче не выше p0, скважина в этом интервале "
                f"закрыта и не добывает (нагнетание не поддержано). Останов "
                f"обычно задают control='rate', q_oil = 0.")
        # q_oil = 0 — намеренный останов (примеры 16, 17): min_bhp при нулевом
        # дебите на итог не влияет, предупреждать не о чем
        elif h.control == "rate" and h.q_oil > 0 and h.min_bhp >= p0:
            user_log.warning(
                f"{where}: min_bhp = {h.min_bhp:.6g} Па ≥ p0 = {p0:.6g} Па при "
                f"q_oil = {h.q_oil:.6g} м³ст/с — забой не может опуститься ниже "
                f"p0, скважина в этом интервале закрыта, дебит не достигается.")
