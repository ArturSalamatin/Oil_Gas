"""Проверка DEBT-013: даёт ли задумка (много интервалов истории) то же, что save_every.

ГИПОТЕЗА. Исходное проектное решение ([[временная-сетка-и-история]]) требует
задавать частоту вывода СТРУКТУРОЙ истории: нужно 72 промежуточных момента —
кладём 72 интервала по 3600 с с одним и тем же p_wf. Реализация вместо этого
ввела save_every, прореживающий подшаги внутри одного интервала.

Скрипт сравнивает два конфига, задающих ФИЗИЧЕСКИ ОДНУ И ТУ ЖЕ задачу:

  A (штатный):  1 интервал 259200 с, dt_integration = 300, save_every = 12
  B (задумка):  72 интервала по 3600 с, dt_integration = 300, save_every = 1

Если состояния совпадают, вариант B — полноценная замена, и save_every
не нужен. Проверяются: моменты времени, забойная температура, давление,
насыщенность.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04a_high_gas_saturation\\diag_intervals.py
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

HERE = Path(__file__).parent


def run(config):
    sim, st0 = SimulatorFactory.from_config(config)
    return sim.run(st0)


def main():
    # ── Вариант A: штатный конфиг с прореживанием ──
    cfg_a = load_config(HERE / "config.json")
    hist_a = run(cfg_a)

    # ── Вариант B: та же задача через структуру истории ──
    # Один интервал 259200 с разбивается на 72 по 3600 с с тем же p_wf.
    # dt_integration остаётся 300 с => внутри каждого интервала 12 подшагов,
    # то есть шаги интегрирования те же самые, что в варианте A.
    cfg_b = load_config(HERE / "config.json")
    iv = cfg_b.time.history[0]
    cfg_b.time.history = [copy.deepcopy(iv) for _ in range(72)]
    for h in cfg_b.time.history:
        h.dt = 3600.0
    cfg_b.output.save_every = 1
    hist_b = run(cfg_b)

    # ── Вариант C: задумка в чистом виде ──
    # Те же 72 интервала, но сохраняются ТОЛЬКО их концы. Текущий код так
    # не умеет: условие simulator.py:170 — "is_last_substep OR счётчик", и
    # при save_every = 1 счётчик срабатывает на каждом подшаге. Огромное
    # save_every глушит вторую половину условия, оставляя только первую,
    # то есть ровно поведение из [[временная-сетка-и-история]].
    cfg_c = load_config(HERE / "config.json")
    iv_c = cfg_c.time.history[0]
    cfg_c.time.history = [copy.deepcopy(iv_c) for _ in range(72)]
    for h in cfg_c.time.history:
        h.dt = 3600.0
    cfg_c.output.save_every = 10**9
    hist_c = run(cfg_c)

    print("== DEBT-013: save_every против структуры истории ==")
    print(f"  A (save_every = 12,  1 интервал):   {len(hist_a.times):3d} записей")
    print(f"  B (save_every = 1,  72 интервала):  {len(hist_b.times):3d} записей")
    print(f"  C (только концы интервалов):        {len(hist_c.times):3d} записей")
    print("  ожидание задумки для B и C: 73 (72 интервала + начальное)")

    if len(hist_a.times) != len(hist_c.times):
        print("  !! A и C дали разное число записей — сравнивать нечего")
        return

    # Дальше сравниваем A и C: оба дают по записи на каждые 3600 с
    hist_b = hist_c

    # Моменты времени должны совпасть точно: оба варианта пишут через 3600 с
    dt_err = np.max(np.abs(np.array(hist_a.times) - np.array(hist_b.times)))
    print(f"  max|t_A - t_B| = {dt_err:.3e} с")

    # Состояния: если шаги интегрирования те же, решения обязаны совпасть
    # с точностью до арифметики (порядок операций Newton не меняется).
    for name, get in (("T", lambda s: s.T), ("p", lambda s: s.p),
                      ("Sg", lambda s: s.Sg)):
        err = max(float(np.max(np.abs(get(a) - get(b))))
                  for a, b in zip(hist_a.states, hist_b.states))
        print(f"  max|{name}_A - {name}_B| по всем шагам = {err:.3e}")

    print(f"\n  T(r_w) финал: A = {hist_a.states[-1].T[0]:.6f} K, "
          f"B = {hist_b.states[-1].T[0]:.6f} K")


if __name__ == "__main__":
    main()
