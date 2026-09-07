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


def run_example(config_path: str | Path, output_dir: str | Path,
                title: str) -> tuple:
    """Полный расчёт одного примера: конфиг → решение → CSV + PNG.

    Возвращает (elapsed, history, grid, config):
      elapsed  — время расчёта, с
      history  — SimulationHistory
      grid     — Grid (сетка)
      config   — SimulatorConfig (разобранный JSON)
    Все выходные файлы кладутся в output_dir (создаётся при необходимости).
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

    _plot_field(history, grid, times_to_plot, "p",
                f"{title}\nПрофили давления",
                output_dir / "pressure_profiles.png")
    _plot_field(history, grid, times_to_plot, "T",
                f"{title}\nПрофили температуры",
                output_dir / "temperature_profiles.png")
    _plot_field(history, grid, times_to_plot, "Sg",
                f"{title}\nПрофили газонасыщенности",
                output_dir / "saturation_profiles.png")

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

    _print_summary(history, elapsed, output_dir)
    return elapsed, history, grid, config


def _plot_field(history, grid, times_to_plot, field: str,
                title: str, path: Path) -> None:
    """Сохранить профиль одного поля в PNG."""
    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, times_to_plot, field=field, ax=ax)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _print_summary(history, elapsed: float, output_dir: Path) -> None:
    """Краткая сводка результатов в консоль."""
    import numpy as np

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
