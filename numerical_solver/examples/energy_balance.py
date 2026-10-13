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

ФИЗИКА ЖИВЁТ В ЯДРЕ: gpn_multiphase_solver/energy/balance.py — и члены,
и сборка рядов (compute_energy_balance, DEBT-011). Здесь — график и отчёт.

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

Ряды баланса собирает ядро: gpn_multiphase_solver/energy/balance.py,
compute_energy_balance (DEBT-011). Здесь две функции:
  plot_energy_balance()    — график и печать поверх compute_energy_balance()
  report_energy_balance()  — обёртка для run_example (конвенция общих модулей)

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\energy_balance.py 03
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
# Прототип radial_blackoil — установленный дистрибутив (DEBT-059), путь к нему не добавляется
for _p in (str(_ROOT), str(_EXAMPLES)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402
from gpn_multiphase_solver.io.output import plot_energy_balance_series  # noqa: E402
from gpn_multiphase_solver.io.figures import save_figure, export_emf  # noqa: E402


def plot_energy_balance(history, grid, config, output_dir: Path):
    """Построить график баланса энергии и вернуть финальную отн. невязку."""
    bal = compute_energy_balance(history)
    # Имя примера берём из пути к конфигу: модуль общий для всех примеров.
    axes = plot_energy_balance_series(
        bal, title=f"Баланс энергии — {Path(config.config_dir).name}")
    fig = axes[0].figure

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "energy_balance.png"
    save_figure(fig, out_path, dpi=130)
    plt.close(fig)
    print(f"Сохранён: {out_path}")

    # Та же нормировка, что в compute_energy_balance: печать и тесты должны
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
    bal = compute_energy_balance(history)

    print("── Баланс энергии ──")
    print(f"  dE финал = {bal['delta_E'][-1]:+.4e} Дж, "
          f"сумма источников = {bal['total'][-1]:+.4e} Дж")
    # Остаток — округления, а не ошибка расщепления: расщепление сказывается
    # на самом T, не на замыкании баланса (BUG-007). С DEBT-043 — 0…5e-15.
    print(f"  относительная невязка = {bal['rel_residual'][-1]:.4e} "
          f"(уровень округлений; дефект члена даёт 1e-3 и выше)")
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

    plot_energy_balance(history, sim.grid, config, folder / "output")
    # Автономный запуск: SVG только что сохранённого рисунка — в EMF (FEAT-026).
    export_emf(folder / "output")
