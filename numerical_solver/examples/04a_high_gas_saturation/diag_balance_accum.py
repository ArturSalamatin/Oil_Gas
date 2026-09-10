"""DEBT-013: баланс энергии с накоплением вкладов на подшагах.

⚠️ ИСТОРИЧЕСКИЙ СКРИПТ. Он обосновывал решение DEBT-013 до его реализации;
накопитель с тех пор живёт в ядре (gpn_multiphase_solver/energy/balance.py),
и его свойства проверяются тестом test_balance_independent_of_history_structure
на каждом прогоне. Скрипт сохранён как воспроизводимый замер.

ИДЕЯ (сформулирована пользователем). На каждом подшаге интегрирования внутри
симулятора известно всё, что нужно балансу: HydroResult (потоки через грани),
состояние до и после шага, и сам шаг dt. Значит вклад за подшаг можно
посчитать НА МЕСТЕ и накопить. В историю на конце интервала кладётся уже
накопленная сумма — и она не зависит от того, насколько крупен шаг истории.

Это было противоположно прежней схеме, где compute_balance ВОССТАНАВЛИВАЛ
вклад постфактум, умножая мгновенный поток с конца интервала на его длину.
Восстановление безнадёжно: замер показал, что и левые прямоугольники (8e-1),
и трапеции (4e-1) далеки от эталона 1e-3, а на крупных шагах трапеции
расходятся вовсе (29). Скрипт того замера (diag_balance_quadrature.py) удалён
после реализации: он сравнивал способы восстановления, а восстанавливать
больше нечего — числа сохранены в README примера и в заметке vault
«баланс энергии накапливается на подшагах а не восстанавливается по истории».

ЧТО МЕРЯЕТ СКРИПТ. Считает баланс на ПОЛНОЙ истории (запись = подшаг), берёт
его ПОШАГОВЫЕ вклады и суммирует их по группам — ровно так, как это делает
накопитель внутри симулятора при разном шаге истории. Если невязка не зависит
от размера группы, накопление решает задачу полностью.

Дополнительно проверяется НЕРАВНОМЕРНАЯ история (мелкий шаг на старте,
крупный на стационаре) — тот режим, ради которого всё и затевается.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04a_high_gas_saturation\\diag_balance_accum.py
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

# Члены баланса, которые compute_balance возвращает кумулятивно
TERMS = ("cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")


def full_history_balance():
    """Прогон 04a с записью каждого подшага + баланс по нему."""
    cfg = load_config(HERE / "config.json")
    # Все 864 подшага в истории. Раньше это давал save_every = 1; после
    # DEBT-013 частоту вывода задаёт только структура history, поэтому
    # интервал делаем равным dt_integration.
    total = sum(h.dt for h in cfg.time.history)
    n = int(round(total / cfg.time.dt_integration))
    iv = copy.deepcopy(cfg.time.history[0])
    cfg.time.history = [copy.deepcopy(iv) for _ in range(n)]
    for h in cfg.time.history:
        h.dt = total / n
    sim, st0 = SimulatorFactory.from_config(cfg)
    hist = sim.run(st0)
    bal = eb.compute_balance(hist, sim._grid, cfg)
    return hist, bal


def regroup(bal, idx):
    """Пересобрать баланс на подмножестве узлов idx, СУММИРУЯ вклады.

    Кумулятивные члены compute_balance уже являются суммами пошаговых
    вкладов. Взять их значения в узлах idx — это ровно то, что сделал бы
    накопитель: вклады всех подшагов внутри крупного шага просуммированы,
    ничего не потеряно.

    Ключевое отличие от нынешней схемы: там на крупном шаге брался ОДИН
    мгновенный поток и умножался на всю длину шага.
    """
    dE = bal["delta_E"][idx]
    total = np.zeros(len(idx))
    for key in TERMS:
        total = total + bal[key][idx]
    resid = dE - total
    scale = np.maximum(np.abs(dE), np.abs(total))
    scale = np.where(scale < 1e-10, 1.0, scale)
    return float(np.max(np.abs(resid) / scale))


def main():
    hist, bal = full_history_balance()
    n = len(hist.times)
    t = np.array(hist.times)

    print("== DEBT-013: баланс с накоплением вкладов на подшагах ==")
    print(f"  сценарий 04a, dt_integration = 300 с, полная история: {n} записей")
    print(f"  эталонная невязка (все подшаги): {abs(bal['rel_residual'][-1]):.3e}")
    print()
    print("  РАВНОМЕРНЫЙ шаг истории (накопление по группам подшагов):")
    print("    прореживание   шаг истории   записей   макс. невязка")

    for stride in (1, 2, 6, 12, 48, 288, 864):
        idx = list(range(0, n, stride))
        if idx[-1] != n - 1:
            idx.append(n - 1)
        dt_hist = (t[1] - t[0]) * stride
        rel = regroup(bal, idx)
        print(f"    каждый {stride:3d}-й   {dt_hist:9.0f} с   {len(idx):7d}   {rel:.3e}")

    # ── Неравномерная история ──
    # Тот самый режим из постановки пользователя: вначале давление и
    # температура меняются резко — пишем часто; дальше стационар — редко.
    print()
    print("  НЕРАВНОМЕРНЫЙ шаг истории (мелкий на старте, крупный на стационаре):")
    idx = [0]
    step = 1
    while idx[-1] < n - 1:
        idx.append(min(idx[-1] + step, n - 1))
        step = min(step * 2, 288)                   # 300 с -> ... -> 1 сут
    rel = regroup(bal, idx)
    print(f"    записей: {len(idx)}, шаг от {t[1]-t[0]:.0f} с до "
          f"{(t[idx[-1]]-t[idx[-2]]):.0f} с")
    print(f"    макс. невязка: {rel:.3e}")

    print()
    print("  Если невязка одинакова во всех строках — накопление вкладов на")
    print("  подшагах делает баланс независимым от структуры истории, включая")
    print("  неравномерную. Тогда защита в compute_balance не нужна вовсе.")


if __name__ == "__main__":
    main()
