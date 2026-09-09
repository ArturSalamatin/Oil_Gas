"""Общий pipeline для всех примеров: JSON-конфиг → Factory → run → CSV + графики.

Каждый пример вызывает run_example() из своего main.py.
Логика вынесена сюда, чтобы main.py примера оставался коротким и читаемым.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

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
from temperature_asymptotics import report_asymptotics  # noqa: E402
from pvt_plot import plot_pvt, report_pvt  # noqa: E402


def run_example(config_path: str | Path, output_dir: str | Path,
                title: str, overlays: dict | None = None) -> tuple:
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
    передают overlays.
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

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Таблицы ──
    save_well_csv(history, output_dir / "well_history.csv")
    save_csv(history, grid, output_dir / "profiles.csv")

    # ── Графики ──
    # 4 момента времени, равномерно по сохранённым шагам: начало,
    # две промежуточные точки и конец расчёта.
    times = history.times
    idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
    times_to_plot = [times[i] for i in sorted(set(idx))]

    overlays = overlays or {}

    # Замкнутое решение по условию GOR = Rs0 не зависит ни от источника PVT,
    # ни от вида ОФП, поэтому подставляется по умолчанию всем двухфазным
    # сценариям. Пример может задать свой overlay — он имеет приоритет.
    two_phase = config.initial_conditions.Rs0 > 0.0
    p_overlay = overlays.get("p") or (make_overlay_pressure(config) if two_phase else None)
    sg_overlay = overlays.get("Sg") or (make_overlay_saturation(config) if two_phase else None)

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
    # При Rs0 = 0 (примеры 01, 02) он тождественно нулевой — рисовать нечего.
    if np.max(history.states[0].Rs) > 0.0:
        # Аналитика Rs = min(Rs_eq(p), Rs0) зависит только от PVT и давления,
        # поэтому применима во ВСЕХ сценариях с газом и включается по
        # умолчанию. Пример может подменить её своим overlay.
        rs_overlay = overlays.get("Rs") or make_overlay_rs(config)
        _plot_field(history, grid, times_to_plot, "Rs",
                    f"{title}\nПрофили газосодержания",
                    output_dir / "rs_profiles.png", rs_overlay, simulator)

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_well_rate(history, ax=ax)
    ax.set_title(f"{title}\nДебиты скважины")
    fig.tight_layout()
    fig.savefig(output_dir / "well_rates.png", dpi=110)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7, 8))
    plot_wellbore_dynamics(history, axes=axes)
    axes[0].set_title(f"{title}\nДинамика на забое")
    fig.tight_layout()
    fig.savefig(output_dir / "wellbore_dynamics.png", dpi=110)
    plt.close(fig)

    # ── ОФП ──
    # Замыкающие кривые k_r(S_g) в остальных графиках не видны, хотя именно
    # они определяют насыщенность в стационаре (условие GOR = Rs0). Рисуем
    # их вместе с рабочим диапазоном расчёта — общий модуль для всех
    # примеров, аналитических и табличных.
    plot_relperm(config, history, output_dir, title)

    # ── PVT ──
    # Свойства флюида в штатных графиках не видны, хотя определяют и профиль
    # давления, и насыщенность: смена PVT-модели в паре 03<->04 меняет дебит
    # на 46 % и фронт разгазирования в 12 раз, а смена ОФП — почти ничего.
    # Передаём simulator целиком (конвенция общих модулей): модуль сам возьмёт
    # у него тот PVT, которым считалась задача, — график обязан показывать
    # ровно то, что видел решатель, а не пересобранную фабрикой копию.
    plot_pvt(config, history, output_dir, title, simulator)

    # ── Баланс энергии ──
    # Интегральная проверка: схема не должна терять и создавать энергию.
    # Считается ВСЕГДА, включая однофазные сценарии — там просто часть
    # членов тождественно нулевая (см. докстринг energy_balance.py).
    # До FEAT-016 баланс имели только 01, 02, 03, 05 (своими копиями
    # скрипта), а 04 и 06-10 не проверялись ничем — именно поэтому BUG-004
    # на шести конфигурациях из десяти прожил незамеченным.
    #
    # Считается безусловно и при любой структуре истории: члены копятся
    # на подшагах внутри решателя (DEBT-013), а не восстанавливаются по
    # записям. Прежнее ветвление по save_every исчезло вместе с параметром.
    print()
    plot_energy_balance(history, grid, config, output_dir)

    _print_summary(history, elapsed, output_dir)

    # ── Проверка Rs ──
    # Печатается после сводки: это уже не результат расчёта, а контроль
    # согласованности PVT с полем давления. Для однофазных сценариев
    # (Rs0 = 0) функция сама сообщает, что проверять нечего.
    if config.initial_conditions.Rs0 > 0.0:
        print()
        report_rs(config, history, simulator._energy._pvt)
        print()
        report_closed(config, history, grid, simulator)

    # ── PVT: числовая сводка ──
    # Безусловно, в отличие от report_rs: у однофазных примеров (Rs0 = 0)
    # B_o и mu_o тоже осмысленны, там вырождена лишь вторая ветвь, и
    # report_pvt сам сообщает об этом вместо того, чтобы молчать.
    print()
    report_pvt(config, history, simulator)

    # ── Стационарная асимптотика температуры ──
    # Телескопическая формула выведена при λ = 0; при λ ≠ 0 она неверна
    # как таковая, и report_asymptotics сам об этом сообщает (единственный
    # такой пример — 10_deep_degassing). Расхождение на штатных 3 сутках
    # отражает незавершённую релаксацию T, а не дефект — за 400 суток оно
    # падает до 1e-11 К.
    print()
    report_asymptotics(config, history, grid, simulator)

    return elapsed, history, grid, config


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
    fig.savefig(path, dpi=110)
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
