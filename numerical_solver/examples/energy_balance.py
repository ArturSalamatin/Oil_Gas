"""Баланс энергии во времени — общая проверка для всех примеров.

Проверка интегральная: она не зависит ни от вида ОФП, ни от источника PVT,
ни от того, какие тепловые эффекты включены в конфиге. Смысл один — схема
не должна терять и создавать энергию. Компоненты (кумулятивные, от t=0 до
t_n):

  ΔE(t)     — изменение запаса тепловой энергии в области
  adiab(t)  — адиабатический источник, φ·Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt
  conv(t)   — чистая конвекция через забой и контур (обе фазы)
  jt(t)     — источник Джоуля–Томсона (обе фазы)
  deg(t)    — скрытая теплота дегазации, -L·mdot
  cond(t)   — кондуктивный поток через контур
  невязка   — ΔE - (adiab + conv + jt + deg + cond)

ФИЗИКА ЖИВЁТ В ЯДРЕ: gpn_multiphase_solver/energy/balance.py. Здесь —
только сборка массивов, график и отчёт.

Вклады накапливаются на каждом подшаге внутри решателя, поэтому баланс
корректен при любой структуре истории, включая неравномерную.
Восстанавливать их постфактум по записям истории (мгновенные потоки ×
шаг между записями) нельзя: это верно, только пока запись = подшаг схемы,
а внутри интервала записи может укладываться сотня подшагов.

ВСЕ ЧЛЕНЫ СЧИТАЮТСЯ БЕЗУСЛОВНО. Никаких ветвлений «этот член нужен только
если в конфиге λ ≠ 0 / L ≠ 0 / μ_JT ≠ 0»: член входит в формулу всегда и
обнуляется арифметикой, когда соответствующий коэффициент равен нулю.
Возвращаемый dict тоже всегда содержит ПОЛНЫЙ набор ключей — нулевые
массивы вместо отсутствующих. Проверка «нужен ли член» не должна зависеть
от того, посмотрел ли автор скрипта в конфиг: член, нулевой в одном
сценарии, ненулевой в другом.

Три функции:
  compute_balance()        — собирает массивы из накопленных в ядре вкладов
  plot_energy_balance()    — строит график поверх compute_balance()
  report_energy_balance()  — обёртка для run_example (конвенция общих модулей)

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\energy_balance.py 03
"""

import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES),
           str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402
from figure_io import save_figure, export_emf  # noqa: E402


# Шесть накапливаемых членов — их считает и складывает
# gpn_multiphase_solver/energy/balance.py на каждом подшаге схемы.
# Остальные три ключа (total, residual, rel_residual) производные:
# они восстанавливаются из этих шести здесь, при сборке.
_CUMULATIVE = ("delta_E", "cum_adiab", "cum_conv",
               "cum_jt", "cum_deg", "cum_cond")


def compute_balance(history, grid, config):
    """Баланс энергии по накопленным на подшагах вкладам (DEBT-013).

    Возвращает dict с массивами длины len(history.times):
      t, delta_E, cum_adiab, cum_conv, cum_jt, cum_deg, cum_cond,
      total, residual, rel_residual

    Набор ключей ПОЛНЫЙ всегда, независимо от конфига: члены, физически
    отсутствующие в сценарии, приходят нулевыми массивами.

    Физика живёт в gpn_multiphase_solver/energy/balance.py: вклады
    считаются на каждом подшаге внутри решателя по тем же коэффициентам,
    что уходят в СЛАУ. Восстановить их по записям истории нельзя —
    при разреженной истории невязка вырастает на три порядка. Здесь
    остаётся только сборка массивов для графика и отчёта.

    grid и config в расчёте больше не участвуют — сохранены в сигнатуре
    ради совместимости с четырьмя вызывающими (plot_energy_balance,
    report_energy_balance и два теста).
    """
    del grid, config  # см. примечание о совместимости сигнатуры выше

    out = {k: np.array([s[k] for s in history.balance])
           for k in _CUMULATIVE}
    out["t"] = np.array(history.times)

    # Производные величины: считаются из накопленных, а не хранятся.
    out["total"] = (out["cum_adiab"] + out["cum_conv"] + out["cum_jt"]
                    + out["cum_deg"] + out["cum_cond"])
    out["residual"] = out["delta_E"] - out["total"]

    # Нормировка — сумма модулей всех членов, включая ΔE. Невязка есть
    # разность больших кумулятивных сумм, и ошибка округления растёт с их
    # модулями, а не с результатом сложения. Нормировка на max(|ΔE|,
    # |Σ членов|) ломается, когда вклады гасят друг друга (нагрев нефти при
    # дросселировании против адиабатики и дегазации: |ΔE| на порядки
    # меньше отдельных членов), и даёт всплески, когда ΔE меняет знак.
    scale = sum(np.abs(out[k]) for k in _CUMULATIVE)
    # t = 0: все члены нулевые, делить не на что.
    scale = np.where(scale < 1e-10, 1.0, scale)
    out["rel_residual"] = np.abs(out["residual"]) / scale

    return out


def plot_energy_balance(history, grid, config, output_dir: Path):
    """Построить график баланса энергии и вернуть финальную отн. невязку."""
    bal = compute_balance(history, grid, config)
    t_days = bal["t"] * S_TO_DAY    # время на графиках — в сутках (FEAT-022)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(t_days, bal["delta_E"], 'k-', linewidth=2,
             label=r"$\Delta E$ (накопление)")
    ax1.plot(t_days, bal["cum_adiab"], 'b--', linewidth=1.5,
             label="адиабатика (кумул.)")
    ax1.plot(t_days, bal["cum_conv"], 'r--', linewidth=1.5,
             label="чистая конвекция (кумул.)")
    ax1.plot(t_days, bal["cum_jt"], 'm--', linewidth=1.5,
             label="Джоуль–Томсон (кумул.)")
    ax1.plot(t_days, bal["cum_deg"], 'c--', linewidth=1.5,
             label="скрытая теплота (кумул.)")
    # Кондукция рисуется всегда: при λ = 0 кривая лежит на нуле, и это
    # наглядно показывает, что член учтён, а не забыт.
    ax1.plot(t_days, bal["cum_cond"], color='olive', linestyle='--',
             linewidth=1.5, label="теплопроводность (кумул.)")
    ax1.plot(t_days, bal["total"], 'g:', linewidth=1.5,
             label="сумма источников")
    ax1.set_ylabel("Энергия, Дж")
    ax1.legend(fontsize=9)
    # Имя примера берём из пути к конфигу: модуль общий для всех примеров.
    ax1.set_title(f"Баланс энергии — {Path(config.config_dir).name}")
    ax1.grid(True, alpha=0.3)
    ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    ax2.plot(t_days, bal["rel_residual"], 'k-', linewidth=1)
    ax2.set_xlabel("Время, сут")
    ax2.set_ylabel(r"|невязка| / $\Sigma$|членов|")
    ax2.set_title("Относительная невязка баланса")
    ax2.grid(True, alpha=0.3)
    ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "energy_balance.png"
    save_figure(fig, out_path, dpi=130)
    plt.close(fig)
    print(f"Сохранён: {out_path}")

    # Та же нормировка, что в compute_balance: печать и тесты должны
    # показывать одно и то же число.
    final_rel = float(bal["rel_residual"][-1])
    # Без символа Δ: консоль Windows под cp1251 его не кодирует и
    # print падает с UnicodeEncodeError, обрывая весь расчёт.
    print(f"  dE финал          = {bal['delta_E'][-1]:+.4e} Дж")
    print(f"  Адиабатика финал  = {bal['cum_adiab'][-1]:+.4e} Дж")
    print(f"  Конвекция финал   = {bal['cum_conv'][-1]:+.4e} Дж")
    print(f"  Джоуль-Томсон     = {bal['cum_jt'][-1]:+.4e} Дж")
    print(f"  Скрытая теплота   = {bal['cum_deg'][-1]:+.4e} Дж")
    print(f"  Теплопроводность  = {bal['cum_cond'][-1]:+.4e} Дж")
    print(f"  Невязка финал     = {bal['residual'][-1]:+.4e} Дж  "
          f"({final_rel:.2e})")
    return final_rel


def report_energy_balance(config, history, grid, simulator) -> dict:
    """Баланс энергии для run_example — конвенция общих модулей.

    simulator, grid и config в расчёте не участвуют: члены баланса уже
    накоплены решателем на подшагах и лежат в history.balance (DEBT-013).
    Аргументы принимаются ради единообразия вызова из run_example.
    """
    bal = compute_balance(history, grid, config)

    print("── Баланс энергии ──")
    print(f"  dE финал = {bal['delta_E'][-1]:+.4e} Дж, "
          f"сумма источников = {bal['total'][-1]:+.4e} Дж")
    print(f"  относительная невязка = {bal['rel_residual'][-1]:.4e}")
    print(f"    (остаток — ошибка расщепления O(dt): гидро-шаг замораживает "
          f"T, тепловой шаг — p и S_g)")
    return bal


def _resolve_example(name_or_prefix: str) -> Path:
    """examples/<имя>/ по полному имени или числовому префиксу ('03').

    Пользователю не нужно печатать '03_standing_corey' целиком.
    Ошибка при отсутствии или неоднозначности префикса.
    """
    exact = _EXAMPLES / name_or_prefix
    if exact.is_dir():
        return exact
    matches = sorted(d for d in _EXAMPLES.iterdir()
                     if d.is_dir() and d.name.startswith(name_or_prefix))
    if not matches:
        raise SystemExit(f"нет примера '{name_or_prefix}'")
    if len(matches) > 1:
        raise SystemExit(f"неоднозначно: {[m.name for m in matches]}")
    return matches[0]


# ── Автономный запуск ──
if __name__ == "__main__":
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory

    if len(sys.argv) < 2:
        raise SystemExit(
            "укажите пример: python examples\\energy_balance.py 03")

    folder = _resolve_example(sys.argv[1])
    config = load_config(folder / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    plot_energy_balance(history, sim._grid, config, folder / "output")
    # Автономный запуск: SVG только что сохранённого рисунка — в EMF (FEAT-026).
    export_emf(folder / "output")
