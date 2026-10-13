"""Конвейер расчёта по конфигу: расчёт → CSV + рисунки + печать проверок (FEAT-030).

Перенесён из examples/example_runner.py: тот же штатный набор, что давал
run_example каждому примеру. Отличия: состав вывода (заголовок, число
профилей, стационарная аналитика, наложения замкнутого решения) берётся
из секции output конфига, аргументы его переопределяют; результат —
CaseResult с решателем; входные файлы внутри каталога вывода — отказ до
расчёта. Режим matplotlib и кодировку консоли модуль не трогает —
cli.configure_batch_run.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from ..factory import SimulatorFactory
from ..grid.base import Grid
from ..io.config import SimulationConfig, load_config
from ..io.figures import export_emf, save_figure
from ..io.output import (plot_profiles, plot_well_rate, plot_wellbore_dynamics,
                         save_csv, save_well_csv)
from ..simulator import Simulator
from ..state import SimulationHistory
from .closed_form import make_overlay_pressure, make_overlay_saturation, report_closed
from .energy_balance import plot_energy_balance
from .mass_balance import plot_mass_balance
from .pvt import plot_pvt, report_pvt
from .relperm import plot_relperm
from .rs import make_overlay_rs, report_rs
from .temperature import report_asymptotics


class CaseConfigError(ValueError):
    """Конфиг не читается, не проходит проверку или не собирается фабрикой; расчёт не начат. FEAT-030."""


class CaseRunError(RuntimeError):
    """Решатель отказал на шаге по времени; результаты прошлого прогона не тронуты. FEAT-030."""


@dataclass
class CaseResult:
    """Итог run_case: решатель, история, сетка, конфиг, заголовок, каталог вывода, время расчёта, с. FEAT-030."""
    elapsed: float
    simulator: Simulator
    history: SimulationHistory
    grid: Grid
    config: SimulationConfig
    title: str
    output_dir: Path


def run_case(config_path: str | Path, output_dir: str | Path | None = None, *,
             title: str | None = None, n_profiles: int | None = None,
             steady_state: bool | None = None,
             overlays: dict | None = None) -> CaseResult:
    """Полный штатный расчёт по конфигу: решение → CSV + PNG + печать проверок. FEAT-030.

    Все выходные файлы кладутся в output_dir (None — папка output рядом с
    конфигом). Каталог очищается целиком после успешного расчёта (решение
    пользователя 2026-10-13); конфиг и его CSV внутри него — отказ до расчёта.

    title, n_profiles, steady_state — None: значение из секции output
    конфига (заголовок по умолчанию — имя папки конфига).

    overlays — необязательные дополнительные кривые на профильных графиках:
    {"p": func(ax, history, grid, simulator), "T": ..., "Sg": ..., "Rs": ...}.
    Функция вызывается после отрисовки численных профилей и может добавить
    на те же оси, например, аналитическое решение. Значение None у ключа
    отключает наложение по умолчанию для этого поля, например {"Sg": None}.

    n_profiles — число моментов на профильных графиках, равномерно по
    времени от начала до конца расчёта (ближайшие записи истории). None —
    четыре опорных момента по номеру записи.

    steady_state — строить ли стационарную аналитику: замкнутое решение
    на профилях p и S_g (каких — output.closed_form_overlays), его сверку
    report_closed и асимптотику температуры report_asymptotics. Все они —
    пределы t -> inf при удержании одного режима скважины. False снимает их;
    явный overlay при этом рисуется. Проверка R_s (наложение и report_rs) от
    флага не зависит.
    """
    config_path = Path(config_path)
    t_start = time.perf_counter()
    # Ошибки чтения и проверки конфига — до печати и до расчёта. TypeError —
    # лишний ключ секции (строгая распаковка dataclass), KeyError —
    # пропущенный ключ внутри секции (time.history).
    try:
        config = load_config(config_path)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise CaseConfigError(f"{config_path}: {exc}") from exc

    out = config.output
    if title is None:
        title = out.title if out.title is not None else config_path.resolve().parent.name
    if n_profiles is None:
        n_profiles = out.n_profiles
    elif isinstance(n_profiles, bool) or not isinstance(n_profiles, int) or n_profiles < 2:
        # Явный аргумент проверяется здесь, а не после расчёта в _profile_times
        raise ValueError(f"n_profiles = {n_profiles!r}: нужно целое не меньше двух")
    if steady_state is None:
        steady_state = out.steady_state
    output_dir = (Path(output_dir) if output_dir is not None
                  else config_path.parent / "output")
    _check_inputs_outside(config_path, config, output_dir)

    print(f"=== {title} ===")
    print(f"Конфиг: {config_path}")

    try:
        simulator, initial_state = SimulatorFactory.from_config(config)
    except (OSError, ValueError) as exc:
        # Таблицы PVT/ОФП не читаются или несогласованы (factory.py) — та
        # же категория: расчёт не начат
        raise CaseConfigError(f"{config_path}: {exc}") from exc
    # Grid нужен для save_csv и профильных графиков (r_centers).
    grid = simulator.grid

    try:
        history = simulator.run(initial_state)
    except RuntimeError as exc:
        # Отказ шага (Simulator._failure_message) или нефизичная T —
        # сообщения решателя написаны для пользователя. Каталог вывода не
        # тронут: очистка — после расчёта.
        raise CaseRunError(str(exc)) from exc

    elapsed = time.perf_counter() - t_start

    # Чистим output/ от результатов прошлых прогонов: иначе файлы, которые
    # текущая конфигурация уже не порождает (например, rs_profiles.png после
    # перехода примера на однофазный режим), остаются лежать и выглядят как
    # актуальные. Удаление ПОСЛЕ расчёта, а не до: если решатель упадёт,
    # прошлые результаты уцелеют.
    if output_dir.is_dir():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Таблицы ──
    save_well_csv(history, output_dir / "well_history.csv")
    save_csv(history, grid, output_dir / "profiles.csv")

    # ── Графики ──
    times_to_plot = _profile_times(history.times, n_profiles)

    overlays = overlays or {}

    # Замкнутое решение по условию GOR = Rs0 не зависит ни от источника PVT,
    # ни от вида ОФП, поэтому подставляется по умолчанию всем двухфазным
    # сценариям. Явный overlay имеет приоритет, а None отключает наложение
    # (см. _pick_overlay).
    two_phase = config.initial_conditions.Rs0 > 0.0
    # Стационарные наложения — только при steady_state: при частой смене
    # режима скважины предела t -> inf у записей нет.
    steady = two_phase and steady_state
    # На каких профилях рисовать замкнутое решение — output.closed_form_overlays
    # (13a: только p; 15: ни на одном). Явный overlay аргумента сильнее.
    fields = out.closed_form_overlays
    p_overlay = _pick_overlay(overlays, "p",
                              make_overlay_pressure(config)
                              if steady and "p" in fields else None)
    sg_overlay = _pick_overlay(overlays, "Sg",
                               make_overlay_saturation(config)
                               if steady and "Sg" in fields else None)

    _plot_field(history, grid, times_to_plot, "p",
                f"{title}\nПрофили давления",
                output_dir / "pressure_profiles.png", p_overlay, simulator)
    _plot_field(history, grid, times_to_plot, "T",
                f"{title}\nПрофили температуры",
                output_dir / "temperature_profiles.png", overlays.get("T"), simulator)
    _plot_field(history, grid, times_to_plot, "Sg",
                f"{title}\nПрофили газонасыщенности",
                output_dir / "saturation_profiles.png", sg_overlay, simulator)

    # Профиль Rs строим только для сценариев с растворённым газом.
    # При Rs0 = 0 он тождественно нулевой — рисовать нечего.
    if np.max(history.states[0].Rs) > 0.0:
        # Аналитика Rs = min(Rs_eq(p), Rs0) зависит только от PVT и давления,
        # поэтому применима во ВСЕХ сценариях с газом и включается по
        # умолчанию. Явный overlay подменяет её или отключает (None).
        rs_overlay = _pick_overlay(overlays, "Rs", make_overlay_rs(config))
        _plot_field(history, grid, times_to_plot, "Rs",
                    f"{title}\nПрофили газосодержания",
                    output_dir / "rs_profiles.png", rs_overlay, simulator)

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_well_rate(history, ax=ax)
    ax.set_title(f"{title}\nДебиты скважины")
    fig.tight_layout()
    save_figure(fig, output_dir / "well_rates.png", dpi=110)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7, 8))
    plot_wellbore_dynamics(history, axes=axes)
    axes[0].set_title(f"{title}\nДинамика на забое")
    fig.tight_layout()
    save_figure(fig, output_dir / "wellbore_dynamics.png", dpi=110)
    plt.close(fig)

    # ── ОФП ──
    # Замыкающие кривые k_r(S_g) в остальных графиках не видны, хотя именно
    # они определяют насыщенность в стационаре (условие GOR = Rs0). Рисуем
    # их вместе с рабочим диапазоном расчёта — для любой модели ОФП,
    # аналитической и табличной. ОФП — объект решателя (DEBT-011), а не
    # пересобранная фабрикой копия.
    plot_relperm(config, history, output_dir, title,
                 relperm=simulator.relperm)

    # ── PVT ──
    # Свойства флюида в штатных графиках не видны, хотя определяют профиль
    # давления, дебит и положение фронта разгазирования сильнее ОФП.
    # Передаём simulator целиком (конвенция общих модулей): модуль сам возьмёт
    # у него тот PVT, которым считалась задача, — график обязан показывать
    # ровно то, что видел решатель, а не пересобранную фабрикой копию.
    plot_pvt(config, history, output_dir, title, simulator)

    # ── Баланс энергии ──
    # Интегральная проверка: схема не должна терять и создавать энергию.
    # Считается ВСЕГДА, включая однофазные сценарии — там просто часть
    # членов тождественно нулевая (см. докстринг report/energy_balance.py).
    #
    # Считается безусловно и при любой структуре истории: члены копятся
    # на подшагах внутри решателя, а не восстанавливаются по записям.
    print()
    plot_energy_balance(history, grid, config, output_dir)

    # ── Баланс массы компонентов (DEBT-039) ──
    # Интегралы потоков через забой и контур копит решатель по всем
    # принятым шагам, запас на записях отдаёт решатель — как у баланса
    # энергии, структура истории проверке не мешает. До export_emf:
    # рисунок попадает в тот же пакет EMF.
    print()
    plot_mass_balance(config, history, output_dir)

    # ── EMF-копии рисунков (FEAT-026) ──
    # Все рисунки run_case уже сохранены (PNG + SVG в emf/):
    # один запуск Inkscape на пакет, а не на каждый рисунок.
    export_emf(output_dir)

    _print_summary(history, elapsed, output_dir)

    # ── Проверка Rs ──
    # Печатается после сводки: это уже не результат расчёта, а контроль
    # согласованности PVT с полем давления. Для однофазных сценариев
    # (Rs0 = 0) функция сама сообщает, что проверять нечего.
    if config.initial_conditions.Rs0 > 0.0:
        print()
        report_rs(config, history, simulator.pvt)
        if steady_state:
            print()
            report_closed(config, history, grid, simulator)

    # ── PVT: числовая сводка ──
    # Безусловно, в отличие от report_rs: у однофазных сценариев (Rs0 = 0)
    # B_o и mu_o тоже осмысленны, там вырождена лишь вторая ветвь, и
    # report_pvt сам сообщает об этом вместо того, чтобы молчать.
    print()
    report_pvt(config, history, simulator)

    # ── Асимптотика температуры (только однофазная зона) ──
    # T = T_ext + μ_JT·(p − p_ext): скорость сокращается, профиль не
    # зависит от дебита. От теплопроводности проверка не зависит и
    # считается при любом λ. Расхождение на коротком расчёте отражает
    # незавершённую релаксацию T, а не дефект.
    #
    # Двухфазной аналитики нет: в адвективной форме схемы стационарное
    # уравнение энергии не сворачивается к крайним граням. Схема
    # верифицируется сверкой матрицы с постановкой и балансом энергии.
    print()
    if steady_state:
        report_asymptotics(config, history, grid, simulator)
    else:
        # Одна строка вместо двух отчётов: без неё пропажа сверок в
        # консоли выглядела бы как сбой подключения модулей. Текст прежний
        # (run_example): его сверяют снимки вывода примеров и тесты.
        print("── Стационарная аналитика отключена (steady_state=False): "
              "замкнутое решение и асимптотика температуры не строятся ──")

    return CaseResult(elapsed=elapsed, simulator=simulator, history=history,
                      grid=grid, config=config, title=title, output_dir=output_dir)


def _check_inputs_outside(config_path: Path, config, output_dir: Path) -> None:
    """Конфиг и его CSV не лежат внутри каталога вывода: его очистка их удалила бы. FEAT-030."""
    # Каталог вывода очищается целиком (shutil.rmtree) после расчёта —
    # решение пользователя 2026-10-13. Узкая защита — от самого опасного
    # случая: --output . из папки конфига стёр бы конфиг и таблицы.
    out = output_dir.resolve()
    names = (config.pvt.oil_pvt_file, config.pvt.gas_pvt_file, config.relperm.file)
    inputs = [config_path] + [config.config_dir / n for n in names if n]
    for f in inputs:
        f = f.resolve()
        if f == out or out in f.parents:
            raise CaseConfigError(
                f"каталог вывода {out} содержит входной файл {f}: после расчёта "
                f"каталог очищается целиком, и файл был бы удалён. Укажите "
                f"другой каталог вывода.")


def _pick_overlay(overlays: dict, key: str, default):
    """Наложение поля key: нет ключа — default, иначе значение аргумента (None — без наложения)."""
    # Не `overlays.get(key) or default`: так явный None молча заменялся бы
    # умолчанием, и отключить стационарное решение было бы нельзя.
    if key in overlays:
        return overlays[key]
    return default


def _profile_times(times, n_profiles: int | None) -> list:
    """Моменты профильных графиков, с: N равномерно по времени или четыре опорных."""
    if n_profiles is None:
        # 4 момента, равномерно по сохранённым шагам: начало,
        # две промежуточные точки и конец расчёта.
        idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
        return [times[i] for i in sorted(set(idx))]
    if n_profiles < 2:
        raise ValueError(f"n_profiles = {n_profiles}: нужно не меньше двух "
                         f"моментов, иначе эволюция не видна")
    # N целевых моментов равномерно ПО ВРЕМЕНИ, для каждого — ближайшая запись истории. По времени, а не по номеру
    # записи: при неравномерной записи номера не равномерны во времени.
    # Повторы убираются — при N больше числа записей остаются все записи.
    t = np.asarray(times, dtype=float)
    targets = np.linspace(t[0], t[-1], n_profiles)
    idx = sorted({int(np.argmin(np.abs(t - x))) for x in targets})
    return [times[i] for i in idx]


def _plot_field(history, grid, times_to_plot, field: str,
                title: str, path: Path, overlay=None, simulator=None) -> None:
    """Сохранить профиль одного поля в PNG.

    overlay — необязательная функция (ax, history, grid, simulator),
    дорисовывающая на те же оси дополнительную кривую (например,
    аналитическое решение). simulator передаётся потому, что аналитике
    бывают нужны объекты решателя (PVT, ОФП).
    """
    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, times_to_plot, field=field, ax=ax)
    if overlay is not None:
        overlay(ax, history, grid, simulator)
        ax.legend(fontsize=8)
    ax.set_title(title)
    fig.tight_layout()
    save_figure(fig, path, dpi=110)
    plt.close(fig)


def _print_summary(history, elapsed: float, output_dir: Path) -> None:
    """Краткая сводка результатов в консоль."""
    last = history.states[-1]
    well = history.well_data[-1]

    print(f"Шагов сохранено: {len(history.times)}")
    print(f"Время расчёта:   {elapsed:.2f} с")
    print(f"p(r_w) финал:    {last.p[0] / 1e6:.3f} МПа")
    print(f"T(r_w) финал:    {last.T[0]:.3f} К")
    print(f"Sg макс:         {np.max(last.Sg):.5f}")
    print(f"Rs мин:          {np.min(last.Rs):.3f} м³ст/м³ст")
    print(f"q_o финал:       {well.q_o_std:.4e} м³ст/с")
    print(f"q_g финал:       {well.q_g_std:.4e} м³ст/с")
    print(f"Результаты:      {output_dir}")
