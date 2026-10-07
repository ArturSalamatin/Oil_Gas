"""DEBT-045: таблица баланса энергии сводного README примеров на текущем коде.

Для каждого примера (папки examples/NN_* с config.json) — тот же расчёт, что
у examples/energy_balance.py и check_energy_balance_all.py, но без рисунков:
  - λ_s / λ_o / λ_g из конфига;
  - относительная невязка и E_конд (cum_cond) на конец расчёта;
  - все кумулятивные члены (4 значащие цифры) — для сверки README отдельных
    примеров;
  - T_{N-1} − T_ext по записям истории: min, max, на конец — для абзаца под
    таблицей («ячейка у контура нагревается выше T_ext»). T_ext = T0
    (factory.py: T_ext=ic.T0). По записям, не по подшагам;
  - у 16 — cum_cond на 15 и 16 сут (начало останова и первые сутки) для
    сверки таблицы README 16.
В конце — строки таблицы README в его формате ($\\pm a.bc\\cdot10^{k}$).

Запуск (из numerical_solver основного каталога или worktree):
    .venv\\Scripts\\python <путь>\\vault\\issues\\debt-045\\probes\\plan_energy_table.py
"""

import sys
import time
from pathlib import Path

import numpy as np

# Код берётся из текущего каталога: запуск из worktree проверяет код worktree.
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    raise SystemExit(f"запускать из каталога numerical_solver, сейчас {SOLVER}")
EXAMPLES = SOLVER / "examples"
for p in (SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", EXAMPLES, SOLVER):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver import factory  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

DAY = 86400.0
TERMS = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")


def tex(x: float, digits: int) -> str:
    """Число в формате README: $\\pm a.bc\\cdot10^{k}$; ноль — «0»."""
    if x == 0.0:
        return "0"
    k = int(np.floor(np.log10(abs(x))))
    m = x / 10.0**k
    # Округление мантиссы может дать 10.0 — перенос в порядок.
    if round(abs(m), digits - 1) >= 10.0:
        k += 1
        m = x / 10.0**k
    return f"${m:.{digits - 1}f}\\cdot10^{{{k}}}$"


def at_time(times: np.ndarray, values: np.ndarray, t: float) -> float:
    """Значение на последней записи с times <= t (записи — концы интервалов)."""
    i = int(np.searchsorted(times, t + 1e-6, side="right")) - 1
    return float(values[max(i, 0)])


def main() -> None:
    print(f"Код: {factory.__file__}")
    names = sorted(d.name for d in EXAMPLES.iterdir()
                   if d.is_dir() and (d / "config.json").is_file()
                   and d.name[0].isdigit())
    rows = []
    for name in names:
        cfg = load_config(EXAMPLES / name / "config.json")
        cfg.output.log_level = "WARNING"
        t0 = time.perf_counter()
        sim, initial = SimulatorFactory.from_config(cfg)
        hist = sim.run(initial)
        wall = time.perf_counter() - t0

        bal = compute_balance(hist, sim._grid, cfg)
        times = np.asarray(hist.times, dtype=float)
        T0 = cfg.initial_conditions.T0
        dT_ext = np.array([s.T[-1] - T0 for s in hist.states])
        lam = (cfg.rock.lambda_solid, cfg.rock.lambda_oil, cfg.rock.lambda_gas)
        rel = float(bal["rel_residual"][-1])
        cond = float(bal["cum_cond"][-1])

        print(f"\n== {name}  ({wall:.1f} с, записей {len(times)}, "
              f"t_end = {times[-1] / DAY:.4g} сут)")
        print(f"  λ = {lam[0]:g} / {lam[1]:g} / {lam[2]:g}")
        print(f"  относительная невязка = {rel:.4e}")
        for key in TERMS:
            print(f"  {key:9s} = {float(bal[key][-1]):+.4e} Дж")
        print(f"  T_(N-1) - T_ext: min {dT_ext.min():+.4e}, "
              f"max {dT_ext.max():+.4e}, конец {dT_ext[-1]:+.4e} К")
        if name.startswith("16"):
            c15 = at_time(times, bal["cum_cond"], 15 * DAY)
            c16 = at_time(times, bal["cum_cond"], 16 * DAY)
            print(f"  16: cum_cond(15 сут) = {c15:+.4e}, "
                  f"cum_cond(16 сут) = {c16:+.4e}, "
                  f"первые сутки останова = {c16 - c15:+.4e}, "
                  f"весь останов = {cond - c15:+.4e} Дж")
        rows.append((name, lam, rel, cond))

    print("\n── Строки таблицы README (относительная невязка, E_конд) ──")
    for name, lam, rel, cond in rows:
        short = name.split("_")[0]
        lam_s = "0" if not any(lam) else f"{lam[0]:g} / {lam[1]:g} / {lam[2]:g}"
        print(f"| {short} | {lam_s} | {tex(rel, 2)} | {tex(cond, 3)} |")


if __name__ == "__main__":
    main()
