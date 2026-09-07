"""Сценарий 01: однофазная фильтрация несжимаемой нефти без эффекта Джоуля-Томсона.

После расчёта на график давления наносится аналитическое решение Дюпюи
(стационарный радиальный приток несжимаемой жидкости):
    p(r) = p_wf + (p_0 - p_wf) / ln(R_e/r_w) · ln(r/r_w)
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from example_runner import run_example  # noqa: E402
from gpn_multiphase_solver.io.output import plot_profiles  # noqa: E402

# energy_balance.py лежит рядом с main.py — добавляем папку примера в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from energy_balance import plot_energy_balance  # noqa: E402


def _add_dupuit_curve(history, grid, config, output_dir: Path, title: str):
    """Перестроить pressure_profiles.png, добавив аналитику Дюпюи пунктиром."""
    r_w = config.geometry.r_well
    R_e = config.geometry.R_ext
    p0 = config.initial_conditions.p0
    p_wf = config.time.history[0].p_wf

    # Формула Дюпюи: p(r) = p_wf + Δp / ln(R_e/r_w) · ln(r/r_w)
    r_an = np.logspace(np.log10(r_w), np.log10(R_e), 200)
    p_an = p_wf + (p0 - p_wf) / np.log(R_e / r_w) * np.log(r_an / r_w)

    # Перестроить график: численное решение + аналитика
    times = history.times
    idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
    times_to_plot = [times[i] for i in sorted(set(idx))]

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_profiles(history, grid, times_to_plot, field="p", ax=ax)

    ax.semilogx(r_an, p_an, 'k--', linewidth=1.5, label="Дюпюи (аналит.)")
    ax.legend()
    ax.set_title(f"{title}\nПрофили давления")
    fig.tight_layout()
    fig.savefig(output_dir / "pressure_profiles.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    here = Path(__file__).parent
    elapsed, history, grid, config = run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="01: однофазная фильтрация без JT",
    )

    _add_dupuit_curve(
        history, grid, config,
        output_dir=here / "output",
        title="01: однофазная фильтрация без JT",
    )
    print("График давления перестроен с аналитикой Дюпюи.")

    # Баланс энергии
    plot_energy_balance(history, grid, config, here / "output")
