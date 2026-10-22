"""DEBT-076: нулевая и отрицательная плотность при ст. у. проходят load_config, фабрику и расчёт молча.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-076\\probes\\density_sign.py

Конфиг примера 18, первые 3 интервала истории (1 мин, 1 сут, 2 сут). Значение
pvt.rho_o_std / pvt.rho_g_std подменяется в словаре после json.load — файлы
не создаются. Печать: T у забоя (центр ячейки 0) и экстремумы T на 2 сут.
"""
import json
import logging
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"каталог решателя: {SOLVER}")

logging.disable(logging.CRITICAL)
import gpn_multiphase_solver.io.config as c  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

CONFIG = SOLVER / "examples" / "18_prototype_input" / "config.json"
CASES = ((None, None), ("rho_o_std", -850.0), ("rho_o_std", 0.0),
         ("rho_g_std", -0.85), ("rho_g_std", 0.0))

orig = json.load
try:
    for key, val in CASES:
        def patched(fp, key=key, val=val):
            d = orig(fp)
            if key:
                d["pvt"][key] = val
            d["time"]["history"] = d["time"]["history"][:3]
            return d
        c.json.load = patched
        cfg = c.load_config(CONFIG)            # отказа нет: знак плотности не проверяется
        sim, st = SimulatorFactory.from_config(cfg)
        h = sim.run(st)
        T = np.asarray(h.states[-1].T)
        label = "исходный конфиг" if key is None else f"pvt.{key} = {val}"
        print(f"{label}: t = {h.times[-1] / 86400:.0f} сут, T(r_w) = {T[0]:.4f} K, "
              f"min T = {T.min():.4f}, max T = {T.max():.4f}")
finally:
    c.json.load = orig
