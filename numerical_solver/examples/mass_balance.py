"""Баланс массы компонентов во времени — общая проверка для всех примеров (DEBT-039).

Схема гидродинамики консервативна: невязки eq:residual_oil, eq:residual_gas
(problem_statement.tex) — изменение запаса компонента в ячейке плюс разность
потоков через её грани. Сумма по ячейкам и шагам сворачивается к забою и
контуру:

  невязка_α(t) = ΔM_α(t) + ∫G_α[N] dt − ∫G_α[0] dt,    ΔM_α = M_α(t) − M_α(0)

  M_o = Σ φV S_o/B_o,   M_g = Σ φV (S_o R_s/B_o + S_g/B_g),   м³ст.

Знак G — от скважины: при добыче ∫G[0] < 0, при притоке с контура ∫G[N] < 0.

ЧТО ПРОВЕРЯЕТ. Не физику — сохранение массы заложено в невязку Ньютона, — а
всё, что стоит между ней и историей: допуск Ньютона, накопленный по шагам;
правки состояния после сходимости; знаки и сопоставление потоков в адаптере;
учёт дробления шага в Simulator. Уровень невязки поэтому — допуск Ньютона,
а не округления, как у баланса энергии: замер при планировании — до 2.9e-8
(пример 15), порог тестов 1e-6. Когда невязка старого состояния ниже
абсолютного допуска Ньютона (1e-11 м³ст/с на ячейку), шаг принимается без
итераций, состояние стоит, а поток через контур копится — невязка растёт
на него линейно (останов 16 после 21 сут: 5.3e-6 м³ст/сут).

ФИЗИКА ЖИВЁТ В ЯДРЕ: интегралы потоков копит gpn_multiphase_solver/
mass_balance.py по всем принятым шагам, запас на записях отдаёт решатель.
Здесь — только сборка массивов, график и печать.

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\mass_balance.py 16
"""

import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
# Прототип radial_blackoil — установленный дистрибутив (DEBT-059), путь к нему не добавляется
for _p in (str(_ROOT), str(_EXAMPLES)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.mass_balance import MASS_KEYS  # noqa: E402
from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402
from figure_io import save_figure, export_emf  # noqa: E402
# Одна копия правила разбора имени примера («16» → 16_well_shut_in)
from energy_balance import _resolve_example  # noqa: E402


def compute_mass_balance(history) -> dict | None:
    """Баланс массы по снимкам истории; None — масса не сохраняется. Ур. (eq:residual_oil)."""
    # Снимки либо все есть, либо все None: Simulator решает один раз, по
    # запасу начального состояния (simulator.py, run).
    if not history.mass_balance or history.mass_balance[0] is None:
        return None
    out = {k: np.array([s[k] for s in history.mass_balance]) for k in MASS_KEYS}
    out["t"] = np.array(history.times)
    for a in ("o", "g"):
        well, ext = out[f"cum_{a}_well"], out[f"cum_{a}_ext"]
        dM = out[f"M_{a}"] - out[f"M_{a}"][0]
        out[f"dM_{a}"] = dM
        # Физические знаки для чтения: добыча и приток с контура > 0.
        # 0.0 − x, а не −x: у примеров без газа печаталось бы −0.0000e+00.
        out[f"prod_{a}"] = 0.0 - well
        out[f"inflow_{a}"] = 0.0 - ext
        # Сумма невязок eq:residual_oil (eq:residual_gas) по ячейкам и шагам:
        # внутренние грани сократились, остались забой и контур
        out[f"residual_{a}"] = dM + ext - well
        # Нормировка — сумма модулей членов, как у баланса энергии
        # (energy_balance.compute_balance). При t = 0 и у газа примеров 01,
        # 02 все члены нулевые: делить не на что, невязка 0.
        scale = np.abs(dM) + np.abs(well) + np.abs(ext)
        scale = np.where(scale > 0.0, scale, 1.0)
        out[f"rel_residual_{a}"] = np.abs(out[f"residual_{a}"]) / scale
    return out


def plot_mass_balance(config, history, output_dir: Path) -> dict | None:
    """График и печать баланса массы; массивы compute_mass_balance. Ур. (eq:residual_oil)."""
    # config — первый аргумент: конвенция общих модулей (plot_relperm,
    # plot_pvt; заметка «проверка выносится в общий модуль...»). Исключение
    # plot_energy_balance(history, grid, config, ...) — историческое.
    bal = compute_mass_balance(history)
    if bal is None:
        print("Баланс массы не считается: решатель не отдаёт запас компонентов")
        return None
    t_days = bal["t"] * S_TO_DAY    # время на графиках — в сутках (FEAT-022)

    # Две колонки, а не одни оси: запасы нефти и газа различаются на два
    # порядка (у 16: 10³ и 10⁵ м³ст), общая шкала спрятала бы нефть.
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    for col, (a, name) in enumerate((("o", "Нефтяной компонент"),
                                     ("g", "Газовый компонент"))):
        ax1, ax2 = axes[0, col], axes[1, col]
        ax1.plot(t_days, bal[f"dM_{a}"], 'k-', linewidth=2,
                 label=r"$\Delta M$ (изменение запаса)")
        # Добыча — широкой полупрозрачной линией под штриховой притока: в
        # стационаре (01, 02) кривые совпадают, и узкая скрылась бы.
        ax1.plot(t_days, bal[f"prod_{a}"], 'r-', linewidth=3, alpha=0.5,
                 label="добыча через забой (кумул.)")
        ax1.plot(t_days, bal[f"inflow_{a}"], 'b--', linewidth=1.5,
                 label="приток через контур (кумул.)")
        ax1.plot(t_days, bal[f"inflow_{a}"] - bal[f"prod_{a}"], 'g:',
                 linewidth=1.5, label="приток − добыча")
        ax1.set_ylabel("Объём, м³ст")
        ax1.set_title(name)
        ax1.legend(fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

        ax2.plot(t_days, bal[f"rel_residual_{a}"], 'k-', linewidth=1)
        ax2.set_xlabel("Время, сут")
        ax2.set_ylabel(r"|невязка| / $\Sigma$|членов|")
        ax2.grid(True, alpha=0.3)
        ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    # Имя примера — из пути к конфигу: модуль общий для всех примеров.
    fig.suptitle(f"Баланс массы компонентов — {Path(config.config_dir).name}")
    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "mass_balance.png"
    save_figure(fig, out_path, dpi=130)
    plt.close(fig)
    print(f"Сохранён: {out_path}")

    # Только ASCII-знаки и кириллица: консоль Windows под cp1251 не
    # кодирует Δ, ³, − и print падает с UnicodeEncodeError
    # (energy_balance.py, plot_energy_balance).
    print("Баланс массы компонентов, м3ст:")
    for a, name in (("o", "Нефть"), ("g", "Газ  ")):
        print(f"  {name}: dM = {bal[f'dM_{a}'][-1]:+.4e}, "
              f"добыча = {bal[f'prod_{a}'][-1]:+.4e}, "
              f"приток с контура = {bal[f'inflow_{a}'][-1]:+.4e}")
        print(f"         невязка финал = {bal[f'residual_{a}'][-1]:+.4e} "
              f"({bal[f'rel_residual_{a}'][-1]:.2e}), max по записям "
              f"{float(np.max(bal[f'rel_residual_{a}'])):.2e}")
    return bal


# ── Автономный запуск ──
if __name__ == "__main__":
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory

    if len(sys.argv) < 2:
        raise SystemExit(
            "укажите пример: python examples\\mass_balance.py 16")

    folder = _resolve_example(sys.argv[1])
    config = load_config(folder / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    plot_mass_balance(config, history, folder / "output")
    # Автономный запуск: SVG только что сохранённого рисунка — в EMF (FEAT-026).
    export_emf(folder / "output")
