"""Общий pipeline для всех примеров: JSON-конфиг → Factory → run → CSV + графики.

Каждый пример вызывает run_example() из своего main.py.
Логика вынесена сюда, чтобы main.py примера оставался коротким и читаемым.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

# ── Кодировка консоли ────────────────────────────────────────
# Консоль Windows по умолчанию cp1251, а вывод примеров содержит символы,
# которых в ней нет: м³ст/с, λ, μ, Φ, ≠, ≡, →, рамки ── в заголовках.
# Любой такой print падает с UnicodeEncodeError и обрывает расчёт — причём
# уже ПОСЛЕ того, как отработал решатель
#
# Переключаем поток на UTF-8 с errors="replace". 
# Файлы (CSV, PNG) пишутся своими
# кодировками и этой строкой не затрагиваются.
#
# run_all.py решает ту же задачу своим _print_safe, но только для
# собственных сообщений — внутрь дочерних процессов защита не проходит.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ── Подключение прототипа radial_blackoil ────────────────────
# Прототип не установлен в venv (pyproject.toml включает только
# gpn_multiphase_solver*), но Factory импортирует его при создании
# PrototypeHydroAdapter. Тесты подключают через tests/conftest.py,
# у примеров conftest нет — добавляем путь сами, тем же механизмом.
# Factory использует ленивые импорты, поэтому достаточно сделать это
# до первого вызова from_config().
_SOLVER_ROOT = Path(__file__).resolve().parents[1]   # numerical_solver/
_PROTO_ROOT = _SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
if not _PROTO_ROOT.is_dir():
    raise RuntimeError(
        f"Не найден каталог прототипа radial_blackoil:\n  {_PROTO_ROOT}\n"
        "Он нужен всем примерам (Factory создаёт PrototypeHydroAdapter).\n"
        "Проверьте, что репозиторий выгружен целиком."
    )
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))

# ── Графики без интерактивного окна ──────────────────────────
# Agg — backend без GUI. Задаётся до импорта pyplot, иначе matplotlib
# успевает выбрать интерактивный backend и падает в консоли/CI.
import numpy as np  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.io.output import (  # noqa: E402
    plot_profiles,
    plot_well_rate,
    plot_wellbore_dynamics,
    save_csv,
    save_well_csv,
)

# Модуль лежит рядом, в examples/; путь к этой папке добавляют сами main.py
# примеров перед импортом example_runner, поэтому импорт по имени работает.
from relperm_plot import plot_relperm  # noqa: E402
from rs_analytics import make_overlay_rs, report_rs  # noqa: E402
from closed_form import (  # noqa: E402
    make_overlay_pressure, make_overlay_saturation, report_closed)
from energy_balance import plot_energy_balance  # noqa: E402
from mass_balance import plot_mass_balance  # noqa: E402
from temperature_asymptotics import report_asymptotics  # noqa: E402
from pvt_plot import plot_pvt, report_pvt  # noqa: E402
from figure_io import save_figure, export_emf  # noqa: E402


def run_example(config_path: str | Path, output_dir: str | Path,
                title: str, overlays: dict | None = None,
                n_profiles: int | None = None,
                steady_state: bool = True) -> tuple:
    """Полный расчёт одного примера: конфиг → решение → CSV + PNG.

    Возвращает (elapsed, history, grid, config):
      elapsed  — время расчёта, с
      history  — SimulationHistory
      grid     — Grid (сетка)
      config   — SimulatorConfig (разобранный JSON)
    Все выходные файлы кладутся в output_dir (создаётся при необходимости).

    overlays — необязательные дополнительные кривые на профильных графиках:
    {"p": func(ax, history, grid), "T": ..., "Sg": ..., "Rs": ...}. Функция
    вызывается после отрисовки численных профилей и может добавить на те же
    оси, например, аналитическое решение. Примеры без аналитики просто не
    передают overlays. Значение None у ключа отключает наложение по
    умолчанию для этого поля, например {"Sg": None}.

    n_profiles — число моментов на профильных графиках, равномерно по
    времени от начала до конца расчёта (ближайшие записи истории). None —
    четыре опорных момента по номеру записи.

    steady_state — строить ли стационарную аналитику: замкнутое решение
    на профилях p и S_g, его сверку report_closed и асимптотику
    температуры report_asymptotics. Все они — пределы t -> inf при
    удержании одного режима скважины. False снимает их (например, когда
    режим меняется каждые сутки); явный overlay примера при этом рисуется.
    Проверка R_s (наложение и report_rs) от флага не зависит.
    """
    config_path = Path(config_path)
    output_dir = Path(output_dir)

    print(f"=== {title} ===")
    print(f"Конфиг: {config_path}")

    t_start = time.perf_counter()

    config = load_config(config_path)
    simulator, initial_state = SimulatorFactory.from_config(config)
    # Grid нужен для save_csv и профильных графиков (r_centers).
    # Factory возвращает только (simulator, initial_state), поэтому
    # берём сетку из симулятора.
    grid = simulator._grid

    history = simulator.run(initial_state)

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
    # сценариям. Пример может задать свой overlay — он имеет приоритет,
    # а None отключает наложение (см. _pick_overlay).
    two_phase = config.initial_conditions.Rs0 > 0.0
    # Стационарные наложения — только при steady_state: при частой смене
    # режима скважины предела t -> inf у записей нет.
    steady = two_phase and steady_state
    p_overlay = _pick_overlay(overlays, "p",
                              make_overlay_pressure(config) if steady else None)
    sg_overlay = _pick_overlay(overlays, "Sg",
                               make_overlay_saturation(config) if steady else None)

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
        # умолчанию. Пример может подменить её своим overlay или отключить (None).
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
    # их вместе с рабочим диапазоном расчёта — общий модуль для всех
    # примеров, аналитических и табличных.
    plot_relperm(config, history, output_dir, title)

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
    # членов тождественно нулевая (см. докстринг energy_balance.py).
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
    # Все рисунки run_example уже сохранены (PNG + SVG в emf/):
    # один запуск Inkscape на пакет, а не на каждый рисунок.
    export_emf(output_dir)

    _print_summary(history, elapsed, output_dir)

    # ── Проверка Rs ──
    # Печатается после сводки: это уже не результат расчёта, а контроль
    # согласованности PVT с полем давления. Для однофазных сценариев
    # (Rs0 = 0) функция сама сообщает, что проверять нечего.
    if config.initial_conditions.Rs0 > 0.0:
        print()
        report_rs(config, history, simulator._energy._pvt)
        if steady_state:
            print()
            report_closed(config, history, grid, simulator)

    # ── PVT: числовая сводка ──
    # Безусловно, в отличие от report_rs: у однофазных примеров (Rs0 = 0)
    # B_o и mu_o тоже осмысленны, там вырождена лишь вторая ветвь, и
    # report_pvt сам сообщает об этом вместо того, чтобы молчать.
    print()
    report_pvt(config, history, simulator)

    # ── Асимптотика температуры (только однофазная зона) ──
    # T = T_ext + μ_JT·(p − p_ext): скорость сокращается, профиль не
    # зависит от дебита. От теплопроводности проверка не зависит и
    # считается при любом λ. Расхождение на штатных 3 сутках отражает
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
        # консоли выглядела бы как сбой подключения модулей.
        print("── Стационарная аналитика отключена (steady_state=False): "
              "замкнутое решение и асимптотика температуры не строятся ──")

    return elapsed, history, grid, config


def _pick_overlay(overlays: dict, key: str, default):
    """Наложение поля key: нет ключа — default, иначе значение примера (None — без наложения)."""
    # Не `overlays.get(key) or default`: так явный None молча заменялся бы
    # умолчанием, и отключить стационарное решение из примера было бы нельзя.
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
    бывают нужны внутренние модули решателя (energy solver, PVT).
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
