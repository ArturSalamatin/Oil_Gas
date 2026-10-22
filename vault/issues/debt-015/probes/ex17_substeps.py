"""DEBT-015, шаг 7: какие часы останова примера 17 дробятся и на сколько подшагов (для README 17).

Обёртка energy.solve пишет (t начала, dt) каждого вызова; вызовы группируются по
шагу интегрирования 3600 с. Печать: часы останова с дроблением (номер часа от начала
останова, сутки останова, число подшагов, наименьший подшаг) и сводка.

Запуск из <W>\\numerical_solver:
    <PY> ..\\vault\\issues\\debt-015\\probes\\ex17_substeps.py
"""
import sys
from collections import defaultdict
from pathlib import Path

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

print(f"код: {Path(gpn_multiphase_solver.__file__).parent}")
cfg = load_config(SOLVER / "examples" / "17_shut_in_strong_cooling" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
calls = []
orig = sim._energy.solve


def solve(hydro_result, state_prev, dt, bc, collect=None):
    calls.append((state_prev.t, dt))
    return orig(hydro_result, state_prev, dt, bc, collect)


sim._energy.solve = solve
sim.run(init)

H, DAY, T_SHUT = 3600.0, 86400.0, 15 * 86400.0
by_step = defaultdict(list)
for t, dt in calls:
    by_step[int((t + 1e-6) // H)].append(dt)
split = {k: v for k, v in by_step.items() if len(v) > 1}
print(f"вызовов энергии {len(calls)}, шагов {len(by_step)}, раздроблено {len(split)}; "
      f"подшагов на шаг {min(map(len, split.values()))}…{max(map(len, split.values()))}; "
      f"наименьший {min(min(v) for v in split.values()):g} с, "
      f"наибольший подшаг раздробленного шага {max(max(v) for v in split.values()):g} с")
for k in sorted(split):
    hour = k - int(T_SHUT // H) + 1          # час останова, с 1
    v = split[k]
    print(f"  час останова {hour:4d} (сутки {(hour - 1) // 24 + 1}): {len(v)} подшагов, "
          f"min {min(v):g} с: {[round(x) for x in v]}")
