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
    """Геометрия скважины и пласта — раздел ``geometry`` файла конфигурации.

    Атрибуты
    --------
    r_well : float
        Радиус скважины r_w, м.
    R_ext : float
        Радиус контура питания r_e, м.
    h : float
        Толщина пласта, м.
    """
    r_well: float    # радиус скважины, м
    R_ext: float     # радиус контура питания, м
    h: float         # мощность пласта, м


# ── Секция grid ──────────────────────────────────────────────

@dataclass
class GridConfig:
    """Сетка — раздел ``grid`` файла конфигурации.

    Атрибуты
    --------
    N : int
        Число ячеек логарифмической сетки между r_w и r_e, целое не меньше 1.
    type : str
        Тип сетки; допустимо только ``"log_radial"`` (умолчание).
    """
    N: int                       # число ячеек
    type: str = "log_radial"     # тип сетки: только "log_radial" (проверка — _validate, DEBT-008)


# ── Секция rock ──────────────────────────────────────────────

@dataclass
class RockConfig:
    """Свойства породы — раздел ``rock`` файла конфигурации.

    Атрибуты
    --------
    porosity : float
        Пористость φ при начальном давлении ``initial_conditions.p0``, доли.
    permeability : float
        Абсолютная проницаемость k, м² (1 мД ≈ 9.869e-16 м²).
    rho_cp_solid : float
        Объёмная теплоёмкость скелета (ρc_p)_s, Дж/(м³·К); умолчание 1.25e6.
    lambda_solid : float
        Теплопроводность скелета, Вт/(м·К); умолчание 1.5.
    lambda_oil : float
        Теплопроводность нефти, Вт/(м·К); умолчание 0.14.
    lambda_gas : float
        Теплопроводность газа, Вт/(м·К); умолчание 0.04.
    compressibility : float
        Сжимаемость порового пространства c_r ≥ 0, 1/Па; умолчание 0.
        Пористость φ(p) = porosity·exp(c_r·(p − p0)).
    """
    porosity: float          # φ, безразмерная
    permeability: float      # k, м²
    # Тепловые свойства породы
    rho_cp_solid: float = 1.25e6    # (ρc_p)_s, Дж/(м³·К)
    lambda_solid: float = 1.5       # λ_s, Вт/(м·К)
    lambda_oil: float = 0.14        # λ_o (фазы), Вт/(м·К)
    lambda_gas: float = 0.04        # λ_g (фазы), Вт/(м·К)
    # Сжимаемость породы: прототип считает φ(p) = porosity·exp(c_r·(p − p0)),
    # porosity задана при начальном давлении initial_conditions.p0 (factory.py,
    # CompressibleRock). Опорного давления в конфиге нет (DEBT-008): пара
    # (φ_ref, p_ref) пересчитывается точно — porosity = φ_ref·exp(c_r·(p0 − p_ref)).
    # Энергия (energy/tridiag.py, DEBT-057): флюид — φ(p) по тому же закону,
    # скелет и λ_eff — porosity при p0 (масса скелета в ячейке постоянна).
    compressibility: float = 0.0    # c_r ≥ 0, 1/Па (_validate, DEBT-068)


# ── Секция pvt ───────────────────────────────────────────────

@dataclass
class PVTConfig:
    """Свойства флюидов (PVT) — раздел ``pvt`` файла конфигурации.

    Атрибуты
    --------
    model : str
        ``"standing"`` — корреляции Стендинга, ``"table"`` — таблицы CSV; при
        таблицах корреляции не используются.
    rho_o_std : float
        Плотность нефти в стандартных условиях, кг/м³, > 0.
    rho_g_std : float
        Плотность газа в стандартных условиях, кг/м³, > 0.
    co_undersaturated : float
        Сжимаемость недонасыщенной нефти c_o ≥ 0, 1/Па, — только для
        корреляций Стендинга; умолчание 0 (при таблицах допустимо только 0).
    mu_o_undersaturated : str
        Вязкость нефти выше давления насыщения для корреляций Стендинга:
        ``"none"`` (умолчание) — только от газосодержания, ``"beal"`` —
        с поправкой Била–Стендинга; при таблицах допустимо только ``"none"``.
    oil_pvt_file : str or None
        Таблица нефти (формат PVTO) — имя файла CSV относительно каталога
        файла конфигурации; только для ``model = "table"``.
    gas_pvt_file : str or None
        Таблица газа — имя файла CSV; только для ``model = "table"``.
    """
    model: str              # "standing" или "table"
    rho_o_std: float        # плотность нефти при ст. условиях, кг/м³; > 0 (_validate, DEBT-076)
    rho_g_std: float        # плотность газа при ст. условиях, кг/м³; > 0 (_validate, DEBT-076)
    # Для Standing. При model = "table" выше p_b B_o и μ_o задаёт таблица:
    # c_o ≠ 0 или μ_o ≠ "none" — отказ create_pvt (factory.py; DEBT-078, FEAT-027)
    co_undersaturated: float = 0.0   # c_o ≥ 0 (_validate, DEBT-078) при p > pb, 1/Па
    mu_o_undersaturated: str = "none"  # μ_o при p > pb: "none" | "beal" (FEAT-027)
    # Для табличного PVT — имена CSV-файлов (относительно JSON)
    oil_pvt_file: Optional[str] = None
    gas_pvt_file: Optional[str] = None


# ── Секция relperm ───────────────────────────────────────────

@dataclass
class RelPermConfig:
    """Относительные фазовые проницаемости (ОФП) — раздел ``relperm`` файла конфигурации.

    Атрибуты
    --------
    model : str
        ``"corey"`` — модель Кори, ``"table"`` — таблица CSV.
    S_or : float
        Остаточная нефтенасыщенность (модель Кори), доли; умолчание 0.2.
    S_gc : float
        Критическая газонасыщенность (модель Кори), доли; умолчание 0.05.
    n_o : float
        Показатель степени ОФП нефти (модель Кори); умолчание 2.
    n_g : float
        Показатель степени ОФП газа (модель Кори); умолчание 2.
    kro_max : float
        Наибольшая ОФП нефти (модель Кори); умолчание 1.
    krg_max : float
        Наибольшая ОФП газа (модель Кори); умолчание 0.8.
    file : str or None
        Таблица ОФП — имя файла CSV относительно каталога файла
        конфигурации; только для ``model = "table"``.
    """
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
    """Тепловые свойства флюидов — раздел ``thermal`` файла конфигурации; величины постоянные.

    Атрибуты
    --------
    c_p_oil : float
        Удельная теплоёмкость нефти, Дж/(кг·К); умолчание 2000.
    c_p_gas : float
        Удельная теплоёмкость газа, Дж/(кг·К); умолчание 1000.
    mu_JT_oil : float
        Коэффициент Джоуля–Томсона нефти, К/Па (обычно < 0); умолчание 0.
    mu_JT_gas : float
        Коэффициент Джоуля–Томсона газа, К/Па (обычно > 0); умолчание 0.
    L_degas : float
        Удельная теплота разгазирования, Дж/кг газа; умолчание 0.
    """
    c_p_oil: float = 2000.0          # Дж/(кг·К)
    c_p_gas: float = 1000.0          # Дж/(кг·К)
    mu_JT_oil: float = 0.0           # К/Па
    mu_JT_gas: float = 0.0           # К/Па
    L_degas: float = 0.0             # Дж/кг газа


# ── Секция initial_conditions ────────────────────────────────

@dataclass
class InitialConfig:
    """Начальное состояние пласта — раздел ``initial_conditions``; однородное, те же значения поддерживаются на контуре питания.

    Атрибуты
    --------
    p0 : float
        Начальное пластовое давление, Па.
    T0 : float
        Начальная пластовая температура, К.
    Rs0 : float
        Начальное газосодержание нефти, м³ст/м³ст; нефть недонасыщенная:
        давление насыщения при Rs0 не выше p0.
    """
    p0: float        # начальное давление, Па
    T0: float        # начальная температура, К
    Rs0: float       # начальное газосодержание, м³ст/м³ст


# ── Секция time ──────────────────────────────────────────────

@dataclass
class HistoryInterval:
    """Интервал режима работы скважины; результаты записываются в его конце.

    Атрибуты
    --------
    dt : float
        Длительность интервала, с.
    control : str
        ``"pressure"`` — заданное забойное давление (умолчание), ``"rate"`` —
        заданный дебит нефти.
    p_wf : float or None
        Забойное давление, Па, > 0; обязательно при ``control = "pressure"``.
    q_oil : float or None
        Дебит нефти в стандартных условиях, м³ст/с, ≥ 0; обязательно при
        ``control = "rate"``; 0 — останов скважины.
    min_bhp : float or None
        Нижний предел забойного давления, Па; обязателен при
        ``control = "rate"``.
    """
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
    """Шаг по времени и режим работы скважины — раздел ``time`` файла конфигурации.

    Атрибуты
    --------
    dt_integration : float
        Шаг интегрирования по времени, с; внутри интервала истории шаг не
        длиннее интервала.
    history : list of HistoryInterval
        Интервалы истории по порядку; краткие формы файла конфигурации
        (``repeat``, ``duration`` и ``dt_out``) уже развёрнуты.
    dt_after_control_change : float or None
        Первый подшаг после пуска скважины (первый интервал истории) и после
        каждой смены её режима, с; дальше подшаг удваивается до
        ``dt_integration``. ``None`` (умолчание) – выключено: первый шаг после
        пуска и смен – полный ``dt_integration``, и погрешность первого
        порядка по времени в первой записи после них не уменьшается (у
        температуры у забоя – до десятых долей К при шагах от 5 мин до 1 ч).
        В примерах 16, 17 и в книге Excel – 0.11 с.
    """
    dt_integration: float                  # шаг интегрирования, с
    history: list[HistoryInterval]         # список интервалов
    # Первый подшаг после пуска (интервал 0, FEAT-039) и смены управления
    # скважиной, с (FEAT-032); null – первый шаг интервала полный. Шаг
    # интервала делится на 2**m до подшага не длиннее этого значения и дальше
    # удваивается (Simulator._advance). Рекомендуется 0.11 с (BUG-026): R_s у
    # забоя после останова задаёт его начало – с 2 с занижен на 6–14 %, с
    # 0.11 с – на 0.2–0.7 % (примеры 16, 17; сценарий VAL-004 при
    # N = 175…700); мельче сетка – нужен меньший h0. Пуску хватает и 1.76 с:
    # первая запись после пуска от h0 <= 1.76 с почти не зависит (план
    # FEAT-039). Каждое уменьшение вдвое добавляет один подшаг.
    dt_after_control_change: Optional[float] = None


# ── Секция numerics ──────────────────────────────────────────

# Поля читают фабрика, адаптер прототипа и Simulator (DEBT-008)
@dataclass
class NumericsConfig:
    """Скин и параметры численного метода — раздел ``numerics`` файла конфигурации; необязателен.

    Атрибуты
    --------
    skin : float
        Скин-фактор скважины ≥ 0; учитывается только в гидродинамике
        (сопротивление забойной грани), в уравнении энергии его нет;
        умолчание 0.
    newton_max_iter : int
        Наибольшее число итераций Ньютона прототипа при фиксированном наборе
        фаз; умолчание 15.
    max_active_set_iter : int
        Наибольшее число проходов набора фаз, включающих газ; умолчание 12.
    rs_switch_tol : float
        Допуск включения газа в ячейке по превышению равновесного
        газосодержания, м³ст/м³ст; умолчание 1e-5.
    sg_switch_tol : float
        Допуск выключения газа по отрицательной газонасыщенности, доли;
        умолчание 1e-9.
    jacobian_mode : str
        Способ построения якобиана прототипа; умолчание ``"grouped"``.
    linear_solver : str
        Решатель линейных систем прототипа; умолчание ``"sparse"``.
    max_retries : int
        Наибольшее число делений шага пополам при несходимости Ньютона:
        наименьший подшаг ``dt_integration / 2**max_retries``; умолчание 9.
    newton_cell_tol : float or None
        Безразмерный допуск сходимости Ньютона по каждой ячейке (невязка
        компонента за шаг, отнесённая к поровому объёму); ``None`` —
        выключено; умолчание 1e-8.
    """
    # Скин-фактор: ≥ 0 (DEBT-056). Входит только в гидродинамику — сопротивлением
    # забойной грани; в уравнение энергии не входит (BUG-029). Предупреждения:
    # s > 0 — о температуре (BUG-029), s > 50 — о доле притока (DEBT-056)
    skin: float = 0.0
    # Лимиты Ньютона прототипа: адаптер передаёт их в каждый advance (DEBT-008).
    # Умолчания — умолчания RadialBlackOilModel.advance (тест test_defaults_match_prototype).
    # Ступень 4 advance (BUG-020, _newton_switching) их не читает: у неё свой предел
    # 40 итераций и один проход набора фаз.
    newton_max_iter: int = 15              # итераций Ньютона при фиксированном наборе фаз
    # Проходов набора фаз с включением газа; проходы, где газ только снимается, не
    # считаются (BUG-028), всего проходов не больше max_active_set_iter + N
    max_active_set_iter: int = 12
    # Допуски переключения фаз прототипа: фабрика передаёт их в конструктор модели
    # (DEBT-008). Газ включается в ячейке при R_s > R_s,eq(p) + rs_switch_tol
    # (м³ст/м³ст), выключается при S_g < −sg_switch_tol. rs_switch_tol — ещё и допуск
    # проверки пересыщения старта (factory._check_undersaturated_start, BUG-017) и
    # проверки R_s (report/rs.py, DEBT-026).
    rs_switch_tol: float = 1e-5
    sg_switch_tol: float = 1e-9
    # Якобиан и решатель СЛАУ прототипа (допустимые значения проверяет его конструктор)
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
    # Предел округления (DEBT-055, eq:newton_cell_floor): неизвестные представимы с шагом
    # ulp, и меру нельзя сделать меньше доли меры вектора |J|·ulp(z) — Ньютон встаёт на
    # 0.1–0.46 её. Это давление в потоках через грани, ~2.2e-16·p·T·λ·Δt/V_p: предел растёт
    # как Δt и у забоя логарифмической сетки как N²/ln²(R_ext/r_w) (с ростом R_ext при том
    # же N — убывает). Строка выше порога проходит, если её невязка не выше её предела
    # (DEBT-067, eq:newton_cell_tol_floor): такой шаг принимается, а не дробится. У 17 при
    # 1e-10 отклонённых шагов 7 против 205, якобианов в 3.1 раза меньше; при 1e-8 предел
    # выше порога лишь у N = 350 с шагом 1 сут (пример 14). Порог ниже ~1e-15 недостижим
    # и с пределом (округление накопления). Предел шага — в тексте отказа. null — выкл.
    # Передаётся прототипу (cell_tol). Допуски абсолютного критерия (atol, rtol) —
    # умолчания прототипа, в конфиге их нет (DEBT-008).
    newton_cell_tol: Optional[float] = 1e-8


# ── Секция output ────────────────────────────────────────────

@dataclass
class OutputConfig:
    """Состав выводимых результатов — раздел ``output`` файла конфигурации; на расчёт не влияет.

    Атрибуты
    --------
    log_level : str
        Уровень подробности журнала решателя: ``DEBUG``, ``INFO`` (умолчание),
        ``WARNING``, ``ERROR``, ``CRITICAL`` без учёта регистра.
    title : str or None
        Заголовок рисунков и сводки; ``None`` — имя каталога файла
        конфигурации (у книги — имя книги).
    n_profiles : int or None
        Число моментов времени на графиках профилей, не меньше двух;
        ``None`` — четыре момента, выбранные по номерам записей.
    steady_state : bool
        Сравнение со стационарным режимом: аналитическое решение на графиках
        профилей, сверка с ним, асимптотика температуры; умолчание ``False``.
        Имеет смысл, только если скважина весь расчёт работает в одном режиме
        и течение успело стать стационарным.
    closed_form_overlays : list of str
        На какие профили наносить аналитическое решение при
        ``steady_state = True``: подмножество ``["p", "Sg"]`` (умолчание).
    """
    # Уровень журнала: DEBUG, INFO, WARNING, ERROR, CRITICAL без учёта регистра (иное
    # значение отвергает _validate, DEBT-008). Формата записи в конфиге нет: файл
    # выбирает вызывающий код (io/output.py: save_npz, save_csv).
    log_level: str = "INFO"
    # save_every удалён (DEBT-013): частоту вывода задаёт структура
    # time.history — второго механизма отбора записей больше нет.

    # Состав штатного вывода run_case и команды расчёта (FEAT-030). Параметры
    # оформления, на расчёт не влияют.
    # Заголовок рисунков и печати; None — имя папки конфига.
    title: Optional[str] = None
    # Число моментов на профильных графиках, равномерно по времени (не меньше
    # двух); None — четыре опорных момента по номеру записи.
    n_profiles: Optional[int] = None
    # Стационарная аналитика: замкнутое решение (наложения на профили p и S_g,
    # сверка report_closed) и асимптотика температуры. Это пределы t -> inf при
    # одном режиме скважины; по умолчанию выключена — в сценарии, где
    # стационар не достигнут, сверка показала бы расхождение, не связанное
    # с точностью расчёта (решение пользователя 2026-10-13).
    steady_state: bool = False
    # На каких профилях рисовать замкнутое решение при steady_state = true:
    # подмножество ["p", "Sg"]. Сверка report_closed печатается при любом.
    closed_form_overlays: list[str] = field(default_factory=lambda: ["p", "Sg"])


# ── Полный конфиг ────────────────────────────────────────────

@dataclass
class SimulationConfig:
    """Конфигурация расчёта — результат :func:`load_config`; единицы — СИ.

    Атрибуты
    --------
    geometry : GeometryConfig
        Геометрия скважины и пласта.
    grid : GridConfig
        Сетка.
    rock : RockConfig
        Свойства породы.
    pvt : PVTConfig
        Свойства флюидов.
    relperm : RelPermConfig
        Относительные фазовые проницаемости.
    thermal : ThermalConfig
        Тепловые свойства флюидов.
    initial_conditions : InitialConfig
        Начальное состояние пласта и условия на контуре питания.
    time : TimeConfig
        Шаг по времени и режим работы скважины.
    numerics : NumericsConfig
        Скин и параметры численного метода.
    output : OutputConfig
        Состав выводимых результатов.
    config_dir : pathlib.Path
        Каталог файла конфигурации: от него отсчитываются имена таблиц CSV.
    """
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


# Поля, удалённые из схемы конфига (DEBT-008): объявлялись, но решатель их не
# читал. Старый конфиг с ними загружается — ключ пропускается с предупреждением:
# результат расчёта от этого не меняется, поле игнорировалось и раньше. Иначе
# с save_every (DEBT-013): его пропуск менял бы состав вывода, поэтому — отказ.
# Неизвестный ключ вне этого списка — по-прежнему ошибка распаковки dataclass.
_NEWTON_TOL_REMOVED = ("допуски абсолютного критерия Ньютона — умолчания прототипа "
                       "(rtol = 1e-8, atol = 1e-11 м³ст/с); условие по ячейке — "
                       "numerics.newton_cell_tol")
_STEP_REMOVED = ("шаг задаёт time.dt_integration, глубину дробления шага — "
                 "numerics.max_retries")
_REMOVED_KEYS = {
    "rock": {"p_ref": "пористость rock.porosity задаётся при начальном давлении p0; "
                      "пару (φ_ref, p_ref) пересчитайте: "
                      "porosity = φ_ref·exp(c_r·(p0 − p_ref))"},
    "time": {"start_day": "время расчёта отсчитывается от начала истории, t = 0"},
    "numerics": {"dt_min": _STEP_REMOVED, "dt_max": _STEP_REMOVED,
                 "newton_rtol": _NEWTON_TOL_REMOVED, "newton_atol": _NEWTON_TOL_REMOVED},
    "output": {"format": "формат записи выбирает вызывающий код "
                         "(io/output.py: save_npz, save_csv)"},
}

# Уровни журнала, которые принимает output.log_level (без учёта регистра)
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _drop_removed_keys(raw: dict) -> list[str]:
    """Удалённые из схемы ключи (DEBT-008): убрать из raw, вернуть тексты предупреждений."""
    messages = []
    for section, keys in _REMOVED_KEYS.items():
        sec = raw.get(section)
        if not isinstance(sec, dict):
            continue
        for key, why in keys.items():
            if key in sec:
                del sec[key]
                messages.append(
                    f"{section}.{key} удалён из конфига (DEBT-008) и пропущен — "
                    f"решатель его не читал, результат не меняется: {why}.")
    return messages


# ── Загрузка ─────────────────────────────────────────────────

def load_config(path: str | Path) -> SimulationConfig:
    """Прочитать файл конфигурации JSON и проверить его.

    Краткие формы этапов ``time.history`` разворачиваются в интервалы.
    После проверки в журнал выводятся предупреждения: ключи, удалённые из
    схемы, большой и положительный скин (в уравнении энергии не
    учитывается), этапы, на которых скважина заведомо закрыта (забойное
    давление не ниже начального пластового).

    Параметры
    ---------
    path : str or pathlib.Path
        Файл конфигурации JSON в кодировке UTF-8. Имена таблиц CSV в нём —
        относительно каталога этого файла.

    Возвращает
    ----------
    SimulationConfig
        Проверенная конфигурация; ``config_dir`` — каталог файла.

    Исключения
    ----------
    OSError
        Файл не читается.
    ValueError
        Ошибка JSON; нет обязательного раздела; недопустимое значение поля
        (в сообщении — имя поля).
    TypeError
        Лишний или пропущенный ключ раздела.
    KeyError
        Нет списка ``time.history``.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    # ── Обязательные секции ──
    for key in ("geometry", "grid", "rock", "pvt", "relperm",
                "thermal", "initial_conditions", "time"):
        if key not in raw:
            raise ValueError(f"Отсутствует обязательная секция '{key}' в {path}")

    # Ключи, удалённые из схемы (DEBT-008), — до распаковки секций: иначе
    # строгая распаковка dataclass дала бы TypeError про лишний аргумент.
    # Предупреждения о них — после _validate (порядок DEBT-056, ниже).
    removed = _drop_removed_keys(raw)

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
    for message in removed:
        user_log.warning(message)
    _warn_large_skin(config)
    _warn_skin_not_in_energy(config)
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

    # grid.N — целое ≥ 1 (DEBT-081); bool исключается явно, как у max_retries.
    # До DEBT-081 здесь было только N < 1, и "N": true проходил и это сравнение
    # (True == 1), и LogRadialGrid (bool — подкласс int): расчёт шёл на сетке из
    # одной ячейки молча. Давление в её центре r_0 = sqrt(r_w·R_ext) (2.24 м в
    # примерах 01, 03) выше, чем у забоя: в примере 03 газ не выделялся вовсе,
    # T_wf — на 1.43 К ниже и в 2.24 м от оси вместо 0.102 м (vault/issues/
    # debt-081/probes/). Строка "100" и null давали TypeError в сравнении без
    # имени поля, 100.0 — отказ LogRadialGrid по-английски при сборке решателя.
    # 100.0 к 100 не приводится: в JSON целое пишется без точки, перевод книги
    # (FEAT-035) пишет int. NaN и inf отсёк _check_numeric_fields выше.
    N = cfg.grid.N
    if isinstance(N, bool) or not isinstance(N, int) or N < 1:
        raise ValueError(f"grid.N должен быть целым ≥ 1, получено {N!r}")

    # grid.type (DEBT-008): фабрика строит только логарифмическую радиальную сетку
    # (LogRadialGrid). До DEBT-008 любое значение проходило молча — расчёт шёл на
    # той же сетке (vault/issues/debt-008/probes/red_state.out.txt).
    if cfg.grid.type != "log_radial":
        raise ValueError(
            f"grid.type: поддерживается только \"log_radial\", получено {cfg.grid.type!r}")

    r = cfg.rock
    if r.porosity <= 0 or r.porosity > 1:
        raise ValueError(f"porosity должна быть в (0, 1], получено {r.porosity}")
    if r.permeability <= 0:
        raise ValueError(f"permeability должна быть > 0, получено {r.permeability}")
    # Сжимаемость порового пространства c_r = (1/φ)·dφ/dp ≥ 0 (DEBT-068,
    # eq:porosity problem_statement.tex): поровый объём упругой породы с ростом
    # давления не уменьшается; c_r < 0 — ошибка знака или другое определение.
    # Загрузчик книги прототипа c_r < 0 отвергает (radial_blackoil/
    # input_reader.py, «cr must be >= 0»); путь JSON → фабрика →
    # CompressibleRock его обходил. Замер до DEBT-068 (vault/issues/debt-068/
    # probes/red_state.out.txt; конфиг примера 18, 2 сут, c_o = 1.2e-9 1/Па):
    # c_r = −4.5e-10 и −1e-9 — расчёт молча, дебит нефти на 1 сут на 6 и 14 %
    # ниже, чем при +4.5e-10; c_r < −c_o — C_p < 0 в недонасыщенной зоне
    # (eq:Cp, механизм BUG-019): −2e-9 и ниже — отказ после дробления шага
    # до dt/512. NaN сюда не доходит (_check_numeric_fields). Верхней границы
    # нет: давление не выше p0, и при c_r ≥ 0 φ(p) ≤ porosity ≤ 1.
    if r.compressibility < 0:
        raise ValueError(
            f"rock.compressibility = {r.compressibility} 1/Па < 0: сжимаемость "
            f"порового пространства c_r = (1/φ)·dφ/dp должна быть ≥ 0 — поровый "
            f"объём с ростом давления не уменьшается (вероятно, ошибка знака)")

    # ── PVT: плотности при ст. у. (DEBT-076), сжимаемость нефти (DEBT-078); P8 §5 ──
    # ρ_o,ст, ρ_g,ст входят в энергию: ρ_o = (ρ_o,ст + R_s·ρ_g,ст)/B_o
    # (eq:rho_oil), ρ_g = ρ_g,ст/B_g (pvt/base.py), массовые потоки фаз
    # (fluxes.py) и интенсивность разгазирования ṁ (eq:mdot,
    # energy/tridiag.py); у Стендинга — ещё и γ_API, γ_g корреляций
    # (pvt/standing.py). Гидродинамика табличного пути их не видит
    # (прототип — в стандартных объёмах), отказа там нет нигде. Замер до
    # DEBT-076 (vault/issues/debt-076/probes/density_sign.out.txt; пример 18,
    # 2 сут): ρ_o,ст = −850 и 0 — охлаждение забоя −3.02 и −1.16 К вместо
    # −0.23 К, ρ_g,ст = −0.85 и 0 — нагрев +0.56 и +0.16 К, молча. На PVT
    # Стендинга (density_sign_standing.out.txt, пример 03) — отказ фабрики
    # без имени поля: «Начальное состояние пересыщено газом», при
    # ρ_o,ст = 0 — ZeroDivisionError. Верхней границы и предупреждений о
    # неправдоподобных значениях нет (решение пользователя); книга Excel
    # требует того же > 0 (FEAT-033). NaN и inf сюда не доходят
    # (_check_numeric_fields).
    pc = cfg.pvt
    for name, value, phase in (("pvt.rho_o_std", pc.rho_o_std, "нефти"),
                               ("pvt.rho_g_std", pc.rho_g_std, "газа")):
        if value <= 0:
            raise ValueError(
                f"{name} = {value} кг/м³: плотность {phase} при стандартных "
                f"условиях (не пластовая) должна быть > 0")

    # Сжимаемость недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p при постоянном
    # R_s ≥ 0 (DEBT-078, eq:co_cg problem_statement.tex): при постоянном составе
    # объём жидкости с ростом давления не растёт — условие механической
    # устойчивости (∂p/∂V)_T < 0; c_o < 0 — ошибка знака. В недонасыщенной зоне
    # C_p = φ(c_r + c_o)/B_g (абзац под eq:c_ot; c_r проверен выше, DEBT-068):
    # при c_o < −c_r C_p < 0 — задача некорректна, неявный шаг вырождается на
    # последовательности Δt. Проверка строже: c_o < 0 отвергается и при
    # c_r > |c_o|. Замер до DEBT-078 (vault/issues/debt-078/probes/
    # audit1_dt_dependence.out.txt; пример 03, Стендинг, c_r = 0, 1 сут):
    # c_o = −1e-9 — при dt_integration 3600 и 1800 с расчёт молча (одно
    # предупреждение фабрики, BUG-019), при 900 с — отказ после дробления шага
    # до dt/512 с советом увеличить max_retries; −3.3e-9 (значение примеров
    # 17, 20 с обратным знаком) — отказ при всех трёх шагах. Проверка — при
    # любой модели PVT: при таблице c_o ≠ 0 отвергает и create_pvt, но позже и
    # без слова о знаке; отрицательная c_o табличных данных — свойство таблицы,
    # о ней предупреждает фабрика (_warn_negative_compressibility, BUG-019).
    # Верхней границы нет: ошибку единиц (1e-5 1/Па вместо 1e-9) проверка не
    # ловит (vault/issues/debt-078/probes/co_magnitude.out.txt).
    if pc.co_undersaturated < 0:
        raise ValueError(
            f"pvt.co_undersaturated = {pc.co_undersaturated} 1/Па < 0: сжимаемость "
            f"недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p должна быть ≥ 0 — объём "
            f"нефти с ростом давления не растёт (вероятно, ошибка знака)")

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
    # λ = 0 допустимо: так отключают теплопроводность (примеры 01, 02)
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

    # dt_after_control_change — первый подшаг после смены управления (FEAT-032);
    # None — выключено. Тип и конечность проверил _check_numeric_fields (DEBT-051):
    # здесь только знак. Верхней границы нет — h0 >= dt выключает нарастание.
    h0 = cfg.time.dt_after_control_change
    if h0 is not None and not h0 > 0.0:
        raise ValueError(
            f"time.dt_after_control_change должен быть положительным числом или null, "
            f"получено {h0!r}")

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

    # Лимиты Ньютона прототипа (DEBT-008; адаптер передаёт их в advance) — целые ≥ 1.
    # bool исключается явно, как у max_retries; NaN отсёк _check_numeric_fields.
    nc = cfg.numerics
    for name in ("newton_max_iter", "max_active_set_iter"):
        v = getattr(nc, name)
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise ValueError(f"numerics.{name} должен быть целым ≥ 1, получено {v!r}")
    # Допуски переключения фаз (DEBT-008; фабрика — в конструктор модели) — > 0.
    # Ноль снял бы запас на шум ~1e-13 горизонтальной ветви PVT-таблицы: газ
    # включался бы в недонасыщенных ячейках, а проверка старта отвергала бы p0
    # на 1 Па ниже p_b. Тип и конечность проверил _check_numeric_fields.
    for name in ("rs_switch_tol", "sg_switch_tol"):
        v = getattr(nc, name)
        if not v > 0:
            raise ValueError(f"numerics.{name} должен быть > 0, получено {v}")

    # output.log_level (DEBT-008): setup_logging (log.py) неизвестное имя молча
    # заменял на INFO — опечатка «DEBG» прятала отладочный вывод.
    lvl = cfg.output.log_level
    if not isinstance(lvl, str) or lvl.upper() not in _LOG_LEVELS:
        raise ValueError(
            f"output.log_level должен быть одним из {', '.join(_LOG_LEVELS)} "
            f"(регистр не важен), получено {lvl!r}")

    # Поля состава вывода (FEAT-030). Тип — явно: секция output не входит в
    # _NUMERIC_SECTIONS, а bool — подкласс int (true в n_profiles — опечатка).
    oc = cfg.output
    if oc.title is not None and (not isinstance(oc.title, str) or not oc.title.strip()):
        raise ValueError(
            f"output.title должен быть непустой строкой или null, получено {oc.title!r}")
    n = oc.n_profiles
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 2):
        raise ValueError(
            f"output.n_profiles должен быть целым ≥ 2 или null, получено {n!r}")
    if not isinstance(oc.steady_state, bool):
        raise ValueError(
            f"output.steady_state должен быть true или false, получено {oc.steady_state!r}")
    ov = oc.closed_form_overlays
    # Нестроковый элемент даёт f not in ("p", "Sg") == True — отказ, а не
    # TypeError; до set() доходят только строки "p", "Sg"
    if (not isinstance(ov, list) or any(f not in ("p", "Sg") for f in ov)
            or len(set(ov)) != len(ov)):
        raise ValueError(
            f'output.closed_form_overlays — список без повторов из "p", "Sg", получено {ov!r}')


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


def _warn_skin_not_in_energy(cfg: SimulationConfig) -> None:
    """Предупреждение при s > 0: скин не входит в уравнение энергии (BUG-029). Ур. (eq:QJT_disc)."""
    # Скин в модели — только сопротивление забойной грани в гидродинамике:
    # проводимость 2πkh/(ln(r_1/r_w) + s) (прототип, well_transmissibility_m3).
    # В уравнении энергии забойная грань при добыче вклада не даёт: JT — с весом
    # Φ⁺ = 0 (eq:QJT_disc), перенос R_s — без состава за гранью (eq:mdot_disc).
    # Поэтому JT-нагрев нефти, охлаждение газа и теплота разгазирования на
    # перепаде скин-зоны в T не входят ни при каком N, и T_wf = T[0] их не
    # содержит (ssec:bc_disc). Знак потери без расчёта не известен: на
    # полуячейке у забоя примера 12 JT (+0.033 К) и дегазация (−0.032 К) почти
    # гасят друг друга (BUG-015). Модель не меняется — только предупреждение
    # (решение пользователя, BUG-029).
    # Доля депрессии на скин-зоне в установившемся однофазном притоке:
    # p_e − p_wf = qμ/(2πkh)·(ln(R_ext/r_w) + s), из них qμ/(2πkh)·s — на скин-зоне.
    s = cfg.numerics.skin
    if s > 0:
        g = cfg.geometry
        ln_re_rw = np.log(g.R_ext / g.r_well)
        share = s / (ln_re_rw + s)
        user_log.warning(
            f"numerics.skin = {s} > 0: скин учитывается только в гидродинамике "
            f"(сопротивление забойной грани). В уравнении энергии его нет: "
            f"дросселирование (эффект Джоуля–Томсона) и разгазирование на перепаде "
            f"давления скин-зоны в температуру не входят, и температура забоя T_wf "
            f"их не содержит. В установившемся однофазном притоке на скин-зону "
            f"приходится {share:.1%} депрессии (s / (ln(R_ext/r_w) + s), "
            f"ln(R_ext/r_w) = {ln_re_rw:.3g}).")


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
