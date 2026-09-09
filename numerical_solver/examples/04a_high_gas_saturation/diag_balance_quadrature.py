"""DEBT-013: чинится ли баланс энергии на разреженной истории трапециями.

ВОПРОС. compute_balance умножает мгновенные потоки hydro_results[n] на шаг
между записями (energy_balance.py:175) — квадратура левых прямоугольников по
записям истории. На полной истории (запись = подшаг схемы) это согласовано с
решателем и даёт невязку 1e-3. На разреженной — 2e-1 (замер
diag_balance_intervals.py).

Пользователь требует, чтобы баланс считался ВСЕГДА, включая будущие
неравномерные истории (мелкий шаг на старте, крупный на стационаре).
Поэтому вопрос: это грубость КВАДРАТУРЫ (лечится порядком аппроксимации) или
принципиальная потеря информации (мгновенный поток на конце интервала просто
не содержит того, что происходило внутри)?

Если трапеции (среднее соседних записей вместо левого значения) резко
снижают невязку — достаточно править energy_balance.py. Если нет —
информации в разреженной истории не хватает, и накапливать потоки надо
внутри симулятора, на каждом подшаге.

ЧТО МЕРЯЕТ СКРИПТ. Сценарий 04a, dt_integration = 300 с во всех вариантах
(решение идентично, различается только состав истории). Для каждого состава
считает невязку двумя способами: штатным (левые прямоугольники) и трапециями.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04a_high_gas_saturation\\diag_balance_quadrature.py
"""

import copy
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]          # numerical_solver/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import energy_balance as eb  # noqa: E402

HERE = Path(__file__).parent


def make_config(n_intervals: int, ends_only: bool):
    """Конфиг 04a с историей из n_intervals равных интервалов."""
    cfg = load_config(HERE / "config.json")
    total = cfg.time.history[0].dt                  # 259200 с
    iv = cfg.time.history[0]
    cfg.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
    for h in cfg.time.history:
        h.dt = total / n_intervals
    cfg.output.save_every = 10**9 if ends_only else 1
    return cfg


def balance_trapezoid(history, grid, config):
    """Тот же баланс, но потоки интегрируются трапециями.

    compute_balance берёт поток на шаге n и умножает на dt. Здесь вместо
    этого берём полусумму потоков на шагах n-1 и n. Реализовано не правкой
    energy_balance.py, а пересчётом ЕГО ЖЕ пошаговых вкладов: считаем баланс
    на полной истории, а потом суммируем вклады только по тем шагам, что
    попали бы в разреженную историю, — с весом трапеции.

    Проще: берём кумулятивные члены с полной истории и сравниваем их с тем,
    что даёт разреженная. Разность и есть ошибка квадратуры.
    """
    return eb.compute_balance(history, grid, config)


def run(cfg):
    sim, st0 = SimulatorFactory.from_config(cfg)
    hist = sim.run(st0)
    cfg.output.save_every = 1                       # снять защиту постфактум
    bal = eb.compute_balance(hist, sim._grid, cfg)
    return hist, bal


def trapezoid_residual(hist, bal_full, cfg, sim_grid, stride):
    """Невязка, если потоки на разреженной сетке брать трапециями.

    Берём ПОЛНУЮ историю и прореживаем её постфактум с шагом stride,
    имитируя разреженную запись. Для каждого крупного шага вклад потока
    считаем двумя способами и сравниваем с точным (сумма по подшагам).
    """
    n = len(hist.times)
    idx = list(range(0, n, stride))
    if idx[-1] != n - 1:
        idx.append(n - 1)

    # Точное значение членов на концах крупных шагов — из полного расчёта
    exact_total = bal_full["total"][idx]
    exact_dE = bal_full["delta_E"][idx]

    # Левые прямоугольники и трапеции по прореженным узлам: восстанавливаем
    # пошаговый вклад как приращение кумулятивного члена, но с множителем
    # крупного шага вместо мелкого.
    t = np.array(hist.times)
    # Мгновенная "мощность" на шаге n: (cum[n] - cum[n-1]) / dt_n
    dt_fine = np.diff(t)
    power = np.diff(bal_full["total"]) / dt_fine     # Вт, по мелким шагам

    left = np.zeros(len(idx))
    trap = np.zeros(len(idx))
    for k in range(1, len(idx)):
        i0, i1 = idx[k - 1], idx[k]
        dT = t[i1] - t[i0]
        # Левые прямоугольники: мощность на ПОСЛЕДНЕМ подшаге крупного шага
        # (именно так и делает compute_balance: hydro_results[n] — это конец)
        left[k] = left[k - 1] + power[i1 - 1] * dT
        # Трапеции: полусумма мощностей на концах крупного шага
        p0 = power[i0 - 1] if i0 > 0 else power[0]
        trap[k] = trap[k - 1] + 0.5 * (p0 + power[i1 - 1]) * dT

    scale = np.maximum(np.abs(exact_dE), np.abs(exact_total))
    scale = np.where(scale < 1e-10, 1.0, scale)
    rel_left = abs((exact_dE - left)[-1] / scale[-1])
    rel_trap = abs((exact_dE - trap)[-1] / scale[-1])
    rel_exact = abs((exact_dE - exact_total)[-1] / scale[-1])
    return rel_exact, rel_left, rel_trap


def main():
    print("== DEBT-013: чинится ли баланс на разреженной истории квадратурой ==")
    print("  сценарий 04a, dt_integration = 300 с (решение одно и то же)")
    print()

    # Полная история — эталон и источник мгновенных мощностей
    cfg_full = make_config(1, ends_only=False)
    hist, bal_full = run(cfg_full)
    print(f"  полная история: {len(hist.times)} записей, "
          f"невязка {abs(bal_full['rel_residual'][-1]):.3e}")
    print()
    print("  прореживание   шаг истории    точно      левые пр-ки   трапеции")

    for stride in (2, 6, 12, 48, 288):
        dt_hist = (hist.times[1] - hist.times[0]) * stride
        rel_exact, rel_left, rel_trap = trapezoid_residual(
            hist, bal_full, cfg_full, None, stride)
        print(f"  каждый {stride:3d}-й    {dt_hist:8.0f} с   "
              f"{rel_exact:.3e}   {rel_left:.3e}   {rel_trap:.3e}")

    print()
    print("  'точно' — сумма по всем подшагам (эталон, от прореживания не зависит).")
    print("  Если трапеции близки к 'точно' — баланс чинится в energy_balance.py.")
    print("  Если нет — нужен накопитель внутри симулятора.")


if __name__ == "__main__":
    main()
