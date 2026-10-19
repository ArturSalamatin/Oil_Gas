"""Конвейер расчёта по конфигу: расчёт → CSV + рисунки + печать проверок (FEAT-030).

Перенесён из examples/example_runner.py: тот же штатный набор, что давал
run_example каждому примеру. Отличия: состав вывода (заголовок, число
профилей, стационарная аналитика, наложения замкнутого решения) берётся
из секции output конфига, аргументы его переопределяют; результат —
CaseResult с решателем; входные файлы внутри каталога вывода — отказ до
расчёта. Режим matplotlib и кодировку консоли модуль не трогает —
cli.configure_batch_run.

Вход — JSON-конфиг или книга ввода Excel (FEAT-036): книга переводится в
output/input/ — вход, по которому расчёт повторяется без книги; каталог
вывода при этом очищается до перевода (решение пользователя 2026-10-18).

Каталог вывода очищается переименованием (DEBT-082): занятый — отказ до
расчёта; занятый во время расчёта по конфигу — результаты в соседнем
каталоге с датой и временем в имени.
"""

from __future__ import annotations

import os
import platform
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from .. import __version__
from ..factory import SimulatorFactory
from ..grid.base import Grid
from ..io.config import SimulationConfig, load_config
from ..io.figures import export_emf, save_figure
from ..io.output import (plot_profiles, plot_well_rate, plot_wellbore_dynamics,
                         save_csv, save_well_csv)
from ..io.workbook_convert import workbook_to_config, write_files
from ..io.xlsx_reader import WorkbookError, read_workbook
from ..log import user_log
from ..simulator import Simulator
from ..state import SimulationHistory
from .closed_form import make_overlay_pressure, make_overlay_saturation, report_closed
from .energy_balance import plot_energy_balance
from .mass_balance import plot_mass_balance
from .pvt import plot_pvt, report_pvt
from .relperm import plot_relperm
from .rs import make_overlay_rs, report_rs
from .temperature import report_asymptotics


# Вход run_case — книга, если расширение файла Excel (FEAT-036). Формат книги —
# .xlsx; .xlsm разбор читает так же, а .xls и .xlsb отвергает с подсказкой,
# как пересохранить, — понятнее отказа загрузчика JSON «Expecting value»
EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls", ".xlsb")
# Подкаталог вывода с переводом книги: config.json и CSV таблиц — вход, по
# которому расчёт повторяется командой run без книги (FEAT-036, решение 3)
INPUT_DIR = "input"


# Исключения и итог run_case — FEAT-030; занятый каталог вывода — DEBT-082;
# книга — FEAT-036
class CaseConfigError(ValueError):
    """Ошибка входа расчёта: конфигурация, таблицы или книга не читаются или не проходят проверку, каталог результатов занят; расчёт не начат."""


class CaseRunError(RuntimeError):
    """Отказ решателя на шаге по времени или нефизичное состояние; прежние результаты расчёта по конфигурации не тронуты, у книги в каталоге результатов только ``input/``."""


@dataclass
class CaseResult:
    """Итог :func:`run_case`.

    Атрибуты
    --------
    elapsed : float
        Время от вызова ``run_case`` до конца расчёта, с.
    simulator : Simulator
        Решатель, выполнивший расчёт; сетка, PVT и ОФП — его свойства.
    history : SimulationHistory
        История расчёта.
    grid : Grid
        Сетка расчёта (то же, что ``simulator.grid``).
    config : SimulationConfig
        Проверенная конфигурация расчёта.
    title : str
        Заголовок рисунков и сводки.
    output_dir : pathlib.Path
        Фактический каталог результатов: если исходный заняли во время
        расчёта — соседний каталог с датой и временем в имени.
    """
    elapsed: float
    simulator: Simulator
    history: SimulationHistory
    grid: Grid
    config: SimulationConfig
    title: str
    output_dir: Path


# Конвейер — FEAT-030. Книга (FEAT-036): каталог вывода очищается до записи
# перевода в output_dir/input/ (решение пользователя 2026-10-18). Конфиг:
# каталог очищается целиком после успешного расчёта (решение пользователя
# 2026-10-13). Занятый каталог (DEBT-082): до расчёта — отказ, во время
# расчёта по конфигу — соседний каталог и предупреждение в журнал.
# versions.txt — FEAT-037. steady_state снимает замкнутое решение (report_closed,
# наложения output.closed_form_overlays) и асимптотику T (report_asymptotics);
# явный overlay рисуется и при False
def run_case(config_path: str | Path, output_dir: str | Path | None = None, *,
             title: str | None = None, n_profiles: int | None = None,
             steady_state: bool | None = None,
             overlays: dict | None = None) -> CaseResult:
    """Штатный расчёт по файлу конфигурации или книге Excel: история, профили, рисунки, печать проверок.

    Тот же набор результатов, что даёт команда ``gpn-solver run``. До
    расчёта печатает заголовок, путь входа и версии, после — сводку и
    проверки: балансы энергии и массы, равновесие газосодержания.

    Параметры
    ---------
    config_path : str or pathlib.Path
        Файл конфигурации JSON или книга ввода Excel (``.xlsx``, ``.xlsm``;
        ``.xls`` и ``.xlsb`` отвергаются с подсказкой пересохранить книгу).
    output_dir : str or pathlib.Path, optional
        Каталог результатов. По умолчанию — ``output`` рядом с файлом
        конфигурации или книгой.
    title : str, optional
        Заголовок рисунков и сводки. По умолчанию — ``output.title``
        конфигурации, если не задан — имя каталога файла конфигурации
        (у книги — имя книги без расширения).
    n_profiles : int, optional
        Число моментов времени на графиках профилей, не меньше двух; моменты
        равномерны по времени (ближайшие записи истории). По умолчанию —
        ``output.n_profiles``, если не задан — четыре момента, выбранные по
        номерам записей.
    steady_state : bool, optional
        Сравнение со стационарным режимом: аналитическое решение на графиках
        профилей, сверка с ним и асимптотика температуры — пределы при
        неограниченном времени для одного режима скважины. По умолчанию —
        ``output.steady_state``. Проверка газосодержания выполняется всегда.
    overlays : dict, optional
        Дополнительные кривые на графиках профилей: ключ ``"p"``, ``"T"``,
        ``"Sg"`` или ``"Rs"`` → функция ``f(ax, history, grid, simulator)``;
        вызывается после построения численных профилей. Значение ``None`` у
        ключа отключает наложение по умолчанию для этого профиля.

    Возвращает
    ----------
    CaseResult
        Решатель, история, сетка, конфигурация, заголовок, фактический
        каталог результатов и время расчёта.

    Исключения
    ----------
    ValueError
        ``n_profiles`` — не целое число или меньше двух; файлы не тронуты.
    CaseConfigError
        Ошибка файла конфигурации, таблиц или книги; входные файлы внутри
        каталога результатов; каталог результатов занят другой программой.
        Расчёт не начат.
    CaseRunError
        Решатель не смог выполнить шаг по времени или получил нефизичное
        состояние.

    Примечания
    ----------
    Каталог результатов очищается целиком: при расчёте по файлу
    конфигурации — после успешного расчёта, при расчёте по книге — до
    расчёта. Перевод книги — файл конфигурации и таблицы CSV в СИ —
    записывается в ``output_dir/input/``; по нему расчёт повторяется без
    книги; при ошибке в каталоге остаётся только ``input/``. Если каталог
    заняли во время расчёта по файлу конфигурации, результаты пишутся в
    соседний каталог ``<имя>_<ГГГГ-ММ-ДД>_<чч-мм-сс>``
    (``CaseResult.output_dir``), прежний не трогается. В каталоге
    результатов — ``versions.txt``: версии решателя, прототипа, Python,
    numpy и scipy.
    """
    config_path = Path(config_path)
    t_start = time.perf_counter()
    # Явный аргумент проверяется до всего, что трогает файлы: у книги
    # каталог вывода очищается до расчёта (FEAT-036)
    if n_profiles is not None and (isinstance(n_profiles, bool)
                                   or not isinstance(n_profiles, int) or n_profiles < 2):
        raise ValueError(f"n_profiles = {n_profiles!r}: нужно целое не меньше двух")
    # ── Книга ввода (FEAT-036) ──
    # Перевод в output/input/ — до чтения конфига; дальше расчёт идёт по
    # переведённому config.json, как по любому конфигу. В печати и
    # сообщениях об ошибках — путь книги: ключ её строки равен пути поля
    # JSON (FEAT-035), и отказ _validate называет строку книги
    workbook = config_path if config_path.suffix.lower() in EXCEL_SUFFIXES else None
    if workbook is not None:
        output_dir = (Path(output_dir) if output_dir is not None
                      else workbook.parent / "output")
        config_path = _translate_workbook(workbook, output_dir)
    source = workbook if workbook is not None else config_path
    # Ошибки чтения и проверки конфига — до печати и до расчёта. TypeError —
    # лишний ключ секции (строгая распаковка dataclass), KeyError —
    # пропущенный ключ внутри секции (time.history).
    try:
        config = load_config(config_path)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise CaseConfigError(f"{source}: {exc}") from exc

    out = config.output
    if title is None:
        title = out.title if out.title is not None else config_path.resolve().parent.name
    if n_profiles is None:
        n_profiles = out.n_profiles
    if steady_state is None:
        steady_state = out.steady_state
    output_dir = (Path(output_dir) if output_dir is not None
                  else config_path.parent / "output")
    if workbook is None:
        # Перевод книги лежит в output/input/ по замыслу; саму книгу
        # проверил _translate_workbook
        _check_inputs_outside(config_path, config, output_dir)
        # Занятый каталог вывода (файл открыт в Excel, консоль в каталоге) —
        # отказ до расчёта, а не трассировка после него (DEBT-082). У книги
        # каталог уже очищен в _translate_workbook
        _check_output_free(output_dir)

    # Версии — после проверки конфига: при его ошибке stdout по-прежнему
    # пуст (test_run_case_config_errors). Тот же список пишется в
    # versions.txt после расчёта (FEAT-037)
    versions = _versions()
    print(f"=== {title} ===")
    print(f"Книга: {workbook}" if workbook is not None else f"Конфиг: {config_path}")
    print("Версии: " + ", ".join(f"{name} {ver}" for name, ver in versions))

    try:
        simulator, initial_state = SimulatorFactory.from_config(config)
    except (OSError, ValueError) as exc:
        # Таблицы PVT/ОФП не читаются или несогласованы (factory.py) — та
        # же категория: расчёт не начат
        raise CaseConfigError(f"{source}: {exc}") from exc
    # Grid нужен для save_csv и профильных графиков (r_centers).
    grid = simulator.grid

    try:
        history = simulator.run(initial_state)
    except RuntimeError as exc:
        # Отказ шага (Simulator._failure_message), нефизичное состояние
        # гидродинамики (DEBT-075) или нефизичная T (DEBT-047) — сообщения
        # решателя написаны для пользователя. Каталог вывода не тронут:
        # очистка — после расчёта (у книги — до него: в каталоге только
        # input/, вход, на котором расчёт остановился).
        raise CaseRunError(str(exc)) from exc

    elapsed = time.perf_counter() - t_start

    # Чистим output/ от результатов прошлых прогонов: иначе файлы, которые
    # текущая конфигурация уже не порождает (например, rs_profiles.png после
    # перехода примера на однофазный режим), остаются лежать и выглядят как
    # актуальные. Удаление ПОСЛЕ расчёта, а не до: если решатель упадёт,
    # прошлые результаты уцелеют. Книга — исключение: каталог очищен до
    # перевода (_translate_workbook), в нём только input/ этого расчёта.
    # Очистка переименованием (_clear_output, DEBT-082): каталог заняли во
    # время расчёта (проверка до расчёта прошла) — ни один файл не удалён,
    # а расчёт не теряется: результаты пишутся в соседний каталог с датой и
    # временем в имени, прежний не тронут (решение пользователя
    # 2026-10-18). Расчёт выполнен — код команды 0, CaseResult.output_dir —
    # новый каталог
    if workbook is None and output_dir.is_dir():
        try:
            _clear_output(output_dir)
        except OSError as exc:
            busy = output_dir
            output_dir = _sibling(busy, time.strftime("_%Y-%m-%d_%H-%M-%S"))
            user_log.warning(f"{_busy_message(busy, exc)}. Результаты записаны в "
                             f"{output_dir}; прежние результаты в {busy} не тронуты.")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Версии (FEAT-037) ──
    # Какой версией получены результаты: решатель и прототип, а также Python,
    # numpy и scipy — от них зависят последние разряды чисел
    (output_dir / "versions.txt").write_text(
        "".join(f"{name} {ver}\n" for name, ver in versions), encoding="utf-8")

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


def _sibling(path: Path, suffix: str) -> Path:
    """Свободное имя <имя каталога><suffix>[-k] рядом с каталогом path; корень диска — CaseConfigError. DEBT-082."""
    # abspath, а не resolve: resolve на сетевом диске и диске subst заменил
    # бы букву диска реальным путём (проба аудита 1), и сообщения назвали бы
    # путь, которого инженер не вводил
    path = Path(os.path.abspath(path))
    # У корня диска (D:\) нет имени: соседнего каталога нет, переименовать
    # корень нельзя, а rmtree стёр бы весь диск. Отказ до любого действия
    if not path.name:
        raise CaseConfigError(
            f"каталог вывода {path} — корень диска: перед записью результатов "
            f"каталог очищается целиком. Укажите подкаталог.")
    k = 0
    while True:
        cand = path.with_name(f"{path.name}{suffix}" + (f"-{k}" if k else ""))
        if not cand.exists():
            return cand
        k += 1


def _busy_message(output_dir: Path, exc: OSError) -> str:
    """Текст отказа очистки каталога вывода: причина ОС и подсказка. DEBT-082."""
    return (f"каталог вывода {output_dir} не удаётся очистить ({exc.strerror or exc}): "
            f"файл в нём открыт в другой программе (например, CSV в Excel) или "
            f"каталог — текущий в консоли. Закройте файл или перейдите в консоли "
            f"в другой каталог")


def _check_output_path(output_dir: Path) -> None:
    """Путь вывода годится под каталог: первый существующий среди него и его предков — каталог, иначе CaseConfigError. DEBT-083."""
    # Опечатка в --output (имя CSV или книги вместо каталога) обнаруживалась
    # только после расчёта: mkdir на файле падает FileExistsError даже с
    # exist_ok, на пути через файл (well_history.csv\sub) — тоже, на
    # несуществующем диске — FileNotFoundError (пробы DEBT-083,
    # vault/issues/debt-083/probes/). Проверка ничего не создаёт. abspath, а
    # не resolve, — как в _sibling: диск subst и сетевой остаются собой
    path = Path(os.path.abspath(output_dir))
    existing = next((p for p in (path, *path.parents) if p.exists()), None)
    if existing is None:
        raise CaseConfigError(
            f"каталог вывода {path}: диск {path.anchor} не найден. Укажите "
            f"другой каталог вывода. Расчёт не начат.")
    if not existing.is_dir():
        head = (f"каталог вывода {path}" if existing == path
                else f"каталог вывода {path} не создать: {existing}")
        raise CaseConfigError(
            f"{head} — файл, а не каталог. Укажите другой каталог вывода. "
            f"Расчёт не начат.")


def _check_output_free(output_dir: Path) -> None:
    """Каталог вывода удаляется целиком: проба переименованием туда и обратно, иначе CaseConfigError. DEBT-082."""
    # Windows не переименовывает каталог, в котором открыт файл без права
    # удаления (так открывает Excel) или который служит текущим каталогом
    # процесса, — и ничего при этом не трогает. rmtree на том же каталоге
    # удалил бы часть файлов, а при консоли в каталоге — все, и только
    # потом упал бы (пробы DEBT-082, vault/issues/debt-082/probes/).
    # Файл, открытый с правом удаления, переименование тоже не пропускает,
    # хотя rmtree прошёл бы, — отказ с запасом. На POSIX переименование
    # проходит, как и rmtree
    if not output_dir.is_dir():
        return
    probe = _sibling(output_dir, f".check-{os.getpid()}")
    try:
        os.rename(output_dir, probe)
    except OSError as exc:
        raise CaseConfigError(
            f"{_busy_message(output_dir, exc)} и повторите расчёт. Расчёт не "
            f"начат, каталог не изменён.") from exc
    try:
        os.rename(probe, output_dir)
    except OSError as exc:
        raise CaseConfigError(
            f"каталог вывода {output_dir} при проверке переименован в {probe} и "
            f"не возвращён ({exc.strerror or exc}): верните ему прежнее имя и "
            f"повторите расчёт.") from exc


def _clear_output(output_dir: Path) -> None:
    """Очистка каталога вывода: переименование в соседний, затем его удаление; OSError переименования — каталог цел. DEBT-082."""
    # Переименование — точка невозврата. Прошло — каталог свободен (см.
    # _check_output_free), удаляется уже переименованный. Не прошло —
    # OSError вызывающему, ни один файл не тронут: прямой rmtree успевал
    # удалить часть файлов до отказа (проба аудита 1 FEAT-036)
    if not output_dir.is_dir():
        return
    trash = _sibling(output_dir, f".old-{os.getpid()}")
    os.rename(output_dir, trash)
    try:
        shutil.rmtree(trash)
    except OSError as exc:
        # Файл открыли в уже переименованном каталоге — почти невозможно, но
        # прежние результаты под чужим именем не должны остаться молча
        user_log.warning(f"прежние результаты перенесены в {trash} и не удалены "
                         f"({exc.strerror or exc}); удалите этот каталог вручную.")


def _translate_workbook(workbook: Path, output_dir: Path) -> Path:
    """Книга → output_dir/input/ (config.json и CSV таблиц), каталог вывода очищается до записи; путь config.json. FEAT-036."""
    # Книга внутри каталога вывода — отказ до чтения: очистка удалила бы её
    # (решение 4 черновика плана; по образцу _check_inputs_outside)
    out, book = output_dir.resolve(), workbook.resolve()
    if book == out or out in book.parents:
        raise CaseConfigError(
            f"каталог вывода {out} содержит книгу {book}: перед расчётом по книге "
            f"каталог очищается целиком, и книга была бы удалена. Укажите "
            f"другой каталог вывода.")
    # Перевод в памяти — до очистки: книга с ошибкой (не .xlsx, значения
    # ячеек) каталог вывода не трогает. Сообщение WorkbookError уже
    # начинается с пути книги
    try:
        config, tables = workbook_to_config(read_workbook(workbook))
    except WorkbookError as exc:
        raise CaseConfigError(str(exc)) from exc
    except FileNotFoundError as exc:
        raise CaseConfigError(f"{workbook}: книга не найдена") from exc
    except OSError as exc:
        raise CaseConfigError(f"{workbook}: {exc.strerror or exc}") from exc
    # Очистка — до записи перевода и до расчёта (решение пользователя
    # 2026-10-18): input/ и результаты в каталоге всегда от одного запуска.
    # Цена: при ошибке конфига или отказе решателя прежних результатов нет,
    # остаётся input/ — вход, на котором расчёт остановился.
    # Очистка переименованием (_clear_output, DEBT-082): каталог занят (файл
    # открыт в Excel, консоль в каталоге) — отказ с подсказкой, ни один файл
    # не удалён; прямой rmtree успевал удалить часть (аудит 1 FEAT-036).
    # Корень диска _clear_output отвергает сам (CaseConfigError)
    try:
        _clear_output(output_dir)
    except OSError as exc:
        raise CaseConfigError(
            f"{_busy_message(output_dir, exc)} и повторите расчёт. Расчёт не "
            f"начат, каталог не изменён.") from exc
    try:
        return write_files(output_dir / INPUT_DIR, config, tables)
    except OSError as exc:
        raise CaseConfigError(f"{output_dir / INPUT_DIR}: {exc.strerror or exc}") from exc


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


def _versions() -> list[tuple[str, str]]:
    """Версии решателя, прототипа, Python, numpy, scipy — пары (имя, номер) для versions.txt и печати. FEAT-037."""
    # Импорт здесь, как во всём пакете: прототип импортируется при сборке
    # задачи, а не при импорте модулей. Номер прототипа — из модуля,
    # который считает задачу, а не из метаданных pip: у редактируемой
    # установки они записаны при pip install -e и отстают от кода, в
    # worktree — принадлежат основному каталогу. build_info.VERSION
    # ('1.0.3') — номер для регрессии прототипа, не номер дистрибутива.
    import radial_blackoil
    import scipy
    return [("gpn-multiphase-solver", __version__),
            ("radial-blackoil", radial_blackoil.__version__),
            ("Python", platform.python_version()),
            ("numpy", np.__version__),
            ("scipy", scipy.__version__)]


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
