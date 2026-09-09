"""DEBT-013: сохранится ли корректность баланса энергии при отказе от save_every.

ВОПРОС. compute_balance берёт шаг из истории (dt_step = t[n] - t[n-1],
energy_balance.py:175), но умножает на него МГНОВЕННЫЕ потоки, взятые из
hydro_results[n] — то есть с последнего подшага интервала. Пока сохраняются
все подшаги схемы, это корректная квадратура: каждый шаг схемы даёт свой
множитель. Если же сохранять только концы интервалов (задумка DEBT-013),
поток последнего подшага умножается на всю длину интервала — квадратура
грубеет, и невязка обязана вырасти.

Защита `if save_every != 1: raise ValueError` (energy_balance.py:124) ловит
это лишь косвенно: она проверяет конфиг, а не фактическую равномерность
истории. После удаления save_every проверять станет нечего, и вопрос в том,
что ставить на её место.

ЧТО МЕРЯЕТ СКРИПТ. Один и тот же физический сценарий 04a, три состава истории:

  A (полная):      1 интервал 259200 с, dt_integration = 300 -> 865 записей
  B (концы, 3600): 72 интервала по 3600 с, только концы     ->  73 записи
  C (концы, 1 сут):  3 интервала по 86400 с, только концы    ->   4 записи

Во всех трёх шаги интегрирования одни и те же (dt_integration = 300 с), то
есть физическое решение идентично — различается только состав вывода.
Печатается относительная невязка баланса для каждого.

ОЖИДАНИЕ. Если невязка растёт от A к C — баланс требует полной истории по
существу, а не из-за save_every, и в плане DEBT-013 нужна замена защиты
(проверка равномерности/полноты истории), а не её удаление.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04a_high_gas_saturation\\diag_balance_intervals.py
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
    """Конфиг 04a с историей из n_intervals равных интервалов.

    ends_only = True глушит счётчик save_every огромным значением, оставляя
    от дизъюнкции simulator.py:170 только is_last_substep — то есть ровно
    задуманное поведение (см. diag_intervals.py, вариант C).
    """
    cfg = load_config(HERE / "config.json")
    total = cfg.time.history[0].dt                  # 259200 с
    iv = cfg.time.history[0]
    cfg.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
    for h in cfg.time.history:
        h.dt = total / n_intervals
    cfg.output.save_every = 10**9 if ends_only else 1
    return cfg


def residual(cfg):
    """Прогон + баланс. Возвращает (число записей, шаг истории, отн. невязка).

    Защиту compute_balance по save_every обходим: она смотрит в конфиг, а нас
    интересует поведение самого баланса на разреженной истории. Для этого
    подменяем значение в объекте конфига уже ПОСЛЕ прогона — на состав
    истории это не влияет, история уже посчитана.
    """
    sim, st0 = SimulatorFactory.from_config(cfg)
    hist = sim.run(st0)
    cfg.output.save_every = 1                       # снять защиту постфактум
    bal = eb.compute_balance(hist, sim._grid, cfg)
    dt_hist = hist.times[1] - hist.times[0]
    return len(hist.times), dt_hist, abs(bal["rel_residual"][-1])


def main():
    cases = [
        ("A  полная история (все подшаги)", make_config(1, ends_only=False)),
        ("B  концы интервалов, 3600 с", make_config(72, ends_only=True)),
        ("C  концы интервалов, 86400 с", make_config(3, ends_only=True)),
    ]

    print("== DEBT-013: баланс энергии при сохранении только концов интервалов ==")
    print("  сценарий 04a, dt_integration = 300 с во всех вариантах")
    print()
    print("  вариант                            записей   шаг истории   отн. невязка")

    for name, cfg in cases:
        n, dt_hist, rel = residual(cfg)
        print(f"  {name:33s} {n:5d}   {dt_hist:9.0f} с   {rel:.3e}")

    print()
    print("  Если невязка растёт с укрупнением шага истории — квадратура")
    print("  потоков требует полной истории, и защиту в compute_balance")
    print("  нужно заменить, а не удалить (см. план DEBT-013).")


if __name__ == "__main__":
    main()
