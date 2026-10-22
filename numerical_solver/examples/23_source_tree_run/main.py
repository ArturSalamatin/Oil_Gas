"""Сценарий 23: расчёт по книге Excel прямо из папки с исходным кодом пошаговыми вызовами функций решателя, затем штатный набор результатов теми же функциями – пакеты решателя и прототипа не устанавливаются."""

import platform
import shutil
import sys
import time
from pathlib import Path

# ── Где лежат решатель и прототип ──
# Пакеты решателя и прототипа не установлены (pip install для них не
# выполнялся), поэтому Python найдёт их, только если их папки есть в sys.path –
# списке папок, в которых он ищет модули. Пути отсчитываются от этого файла:
# он лежит в examples\23_source_tree_run\, на два уровня ниже папки с исходным
# кодом, и пример работает из любой копии папки без правки. insert(0, ...)
# ставит папку в начало списка, раньше установленных пакетов
HERE = Path(__file__).resolve().parent      # папка примера
SOURCE = HERE.parent.parent                 # папка с исходным кодом
sys.path.insert(0, str(SOURCE))                                               # решатель
sys.path.insert(0, str(SOURCE / "HydroSolverPrototype" / "Prototype_1.0.3"))  # прототип

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import scipy  # noqa: E402

import gpn_multiphase_solver  # noqa: E402
import radial_blackoil  # noqa: E402
from gpn_multiphase_solver.cli import configure_batch_run  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.io.figures import export_emf, save_figure  # noqa: E402
from gpn_multiphase_solver.io.output import (  # noqa: E402
    plot_profiles, plot_well_rate, plot_wellbore_dynamics, save_csv, save_well_csv)
from gpn_multiphase_solver.io.workbook_convert import convert_workbook  # noqa: E402
from gpn_multiphase_solver.report.energy_balance import plot_energy_balance  # noqa: E402
from gpn_multiphase_solver.report.mass_balance import plot_mass_balance  # noqa: E402
from gpn_multiphase_solver.report.pvt import plot_pvt, report_pvt  # noqa: E402
from gpn_multiphase_solver.report.relperm import plot_relperm  # noqa: E402
from gpn_multiphase_solver.report.rs import make_overlay_rs, report_rs  # noqa: E402

BOOK = HERE / "23_source_tree_run.xlsx"     # книга ввода – шаблон с демонстрационными значениями
OUT = HERE / "output"                       # каталог результатов


def plot_field(history, grid, times, field, title, path, overlay=None, simulator=None):
    """Профили поля field на моментах times – в PNG (и SVG в output\\emf\\ для EMF)."""
    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, times, field=field, ax=ax)
    # Наложение – своя кривая поверх численных профилей: overlay(ax, history, grid, simulator)
    if overlay is not None:
        overlay(ax, history, grid, simulator)
        ax.legend(fontsize=8)
    ax.set_title(title)
    fig.tight_layout()
    save_figure(fig, path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    # Рисунки – в файлы, без окон; русские буквы в консоли – без ошибок
    configure_batch_run()

    # Откуда взяты пакеты: обе строки – из этой папки с исходным кодом
    print("Решатель:", gpn_multiphase_solver.__version__, gpn_multiphase_solver.__file__)
    print("Прототип:", radial_blackoil.__version__, radial_blackoil.__file__)

    # ── Перевод книги и расчёт ──
    # Перевод книги пишется в новый или пустой каталог: результаты прошлого
    # запуска удаляются целиком
    if OUT.exists():
        shutil.rmtree(OUT)
    t_start = time.perf_counter()
    config_path = convert_workbook(BOOK, OUT / "input")              # книга → config.json и CSV в СИ
    config = load_config(config_path)                                # прочитать и проверить
    simulator, initial_state = SimulatorFactory.from_config(config)  # собрать решатель
    history = simulator.run(initial_state)                           # рассчитать
    elapsed = time.perf_counter() - t_start
    grid = simulator.grid
    title = config.output.title                 # у книги – её имя без расширения

    # Таблица по моментам записи: время, забойные давление и температура, дебит нефти
    print(f"{'t, сут':>10}  {'p_wf, бар':>9}  {'T_wf, К':>8}  {'q_o, м³ст/сут':>13}")
    for t, well in zip(history.times, history.well_data):
        print(f"{t / 86400:10.4f}  {well.p_wf / 1e5:9.1f}  {well.T_wf:8.3f}  "
              f"{well.q_o_std * 86400:13.3f}")
    print(f"Записей: {len(history.times)}, время расчёта: {elapsed:.1f} с")

    # ── Версии и таблицы ──
    # Какими версиями получены результаты: от numpy и scipy зависят последние разряды чисел
    versions = [("gpn-multiphase-solver", gpn_multiphase_solver.__version__),
                ("radial-blackoil", radial_blackoil.__version__),
                ("Python", platform.python_version()),
                ("numpy", np.__version__), ("scipy", scipy.__version__)]
    (OUT / "versions.txt").write_text("".join(f"{n} {v}\n" for n, v in versions),
                                      encoding="utf-8")
    save_well_csv(history, OUT / "well_history.csv")      # история скважины
    save_csv(history, grid, OUT / "profiles.csv")         # поля по ячейкам на каждой записи

    # ── Профили по радиусу ──
    # Четыре момента: первая запись, треть и две трети списка записей, последняя
    n = len(history.times)
    times = [history.times[i] for i in sorted({0, n // 3, 2 * n // 3, n - 1})]
    plot_field(history, grid, times, "p", f"{title}\nПрофили давления",
               OUT / "pressure_profiles.png")
    plot_field(history, grid, times, "T", f"{title}\nПрофили температуры",
               OUT / "temperature_profiles.png")
    plot_field(history, grid, times, "Sg", f"{title}\nПрофили газонасыщенности",
               OUT / "saturation_profiles.png")
    # Газосодержание – при растворённом газе; поверх – R_s^eq(p) в ячейках с газом,
    # R_s0 и фронт разгазирования
    if np.max(history.states[0].Rs) > 0.0:
        plot_field(history, grid, times, "Rs", f"{title}\nПрофили газосодержания",
                   OUT / "rs_profiles.png", make_overlay_rs(config), simulator)

    # ── Скважина: дебиты и динамика у забоя ──
    fig, ax = plt.subplots(figsize=(7, 5))
    plot_well_rate(history, ax=ax)
    ax.set_title(f"{title}\nДебиты скважины")
    fig.tight_layout()
    save_figure(fig, OUT / "well_rates.png", dpi=110)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7, 8))
    plot_wellbore_dynamics(history, axes=axes)
    axes[0].set_title(f"{title}\nДинамика на забое")
    fig.tight_layout()
    save_figure(fig, OUT / "wellbore_dynamics.png", dpi=110)
    plt.close(fig)

    # ── ОФП и PVT: модели расчёта и рабочий диапазон ──
    plot_relperm(config, history, OUT, title, relperm=simulator.relperm)
    plot_pvt(config, history, OUT, title, simulator)

    # ── Балансы энергии и массы: рисунок и печать итогов ──
    print()
    plot_energy_balance(history, grid, config, OUT, title)
    print()
    plot_mass_balance(config, history, OUT, title)

    # ── Векторные копии рисунков: SVG уже в output\emf\, EMF – через Inkscape ──
    export_emf(OUT)

    # ── Проверки: равновесие R_s и характеристики PVT на рабочем диапазоне ──
    # Стационарная аналитика (замкнутое решение, асимптотика температуры) не
    # строится: в книге нет листа OUTPUT, steady_state = false
    print()
    report_rs(config, history, simulator.pvt)
    print()
    report_pvt(config, history, simulator)
    print()
    print("Результаты:", OUT)
