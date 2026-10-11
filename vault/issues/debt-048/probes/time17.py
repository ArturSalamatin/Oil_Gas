"""DEBT-048, шаг 5: время расчёта примера 17 для README — целиком, по частям истории, при суточном шаге.

README 17 (раздел «Шаг интегрирования и время расчёта») цитирует время расчёта
при dt_integration = 1 ч и 1 сут и долю первых трёх суток останова. Варианты
штатного конфига examples/17_shut_in_strong_cooling/config.json:
  full   — как есть: добыча 15 сут, останов 1 сут (записи по часам) + 14 сут;
  prod   — только добыча (15 сут);
  shut3  — добыча и первые 3 сут останова (второй блок останова — 2 сут);
  daily  — как есть, но dt_integration = 86400 с.
Время — как строка «Время расчёта» example_runner: load_config + фабрика +
Simulator.run, без рисунков. Запускать без параллельных расчётов.

Дерево кода — как у stage_memory.py (DEBT048_SOLVER или дерево пробы); строка
«код:» вывода должна вести в worktree.

Запуск (из <W>\\numerical_solver): python ..\\vault\\issues\\debt-048\\probes\\time17.py
Вывод: time17<TAG>.out.txt.
"""

import copy
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_memory as sm  # noqa: E402  (ставит sys.path на numerical_solver и прототип)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CONFIG = sm.SOLVER / "examples" / "17_shut_in_strong_cooling" / "config.json"
DAY = 86400.0


def variants(raw):
    """Варианты конфига: имя → словарь JSON."""
    out = {"full": raw}
    prod = copy.deepcopy(raw)
    prod["time"]["history"] = prod["time"]["history"][:1]
    out["prod"] = prod
    shut3 = copy.deepcopy(raw)
    shut3["time"]["history"][2]["duration"] = 2 * DAY
    out["shut3"] = shut3
    daily = copy.deepcopy(raw)
    daily["time"]["dt_integration"] = DAY
    out["daily"] = daily
    return out


def run(raw, name):
    """Время расчёта варианта, с; T(r_w) последней записи, К."""
    path = HERE / f"_time17_{name}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    try:
        t0 = time.perf_counter()
        sim, init = SimulatorFactory.from_config(load_config(path))
        hist = sim.run(init)
        elapsed = time.perf_counter() - t0
    finally:
        path.unlink()
    return elapsed, float(hist.states[-1].T[0])


def main():
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    lines = [sm.code_paths()]
    res = {}
    for name, cfg in variants(raw).items():
        res[name] = run(cfg, name)
        lines.append(f"{name:<6} {res[name][0]:7.2f} с   T(r_w) кон. = {res[name][1]:.3f} К")
        print(lines[-1], flush=True)
    full, prod, shut3 = res["full"][0], res["prod"][0], res["shut3"][0]
    lines.append(f"добыча {prod / full:.0%} времени; первые 3 сут останова "
                 f"{(shut3 - prod) / full:.0%}; остальные 12 сут останова {(full - shut3) / full:.0%}")
    text = "\n".join(lines)
    print(lines[-1])
    (HERE / f"time17{sm.TAG}.out.txt").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
