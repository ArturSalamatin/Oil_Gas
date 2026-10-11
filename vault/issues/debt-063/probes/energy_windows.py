"""DEBT-063, проба: члены баланса энергии по окнам останова (README 16, 17) при обеих формулах центров.

README 16 и 17 («Откуда нагрев», «Откуда тепло на останове») дают члены
баланса энергии за первые сутки останова и за весь останов. Останов
начинается в t = 15 сут (конец первого объекта истории). Член окна —
разность накопленных величин (examples/energy_balance.compute_balance) на
концах окна. Печать — для центров exp<ln r> (как сейчас) и √ (DEBT-063).

Запуск из numerical_solver/:  .venv\\Scripts\\python ..\\vault\\issues\\debt-063\\probes\\energy_windows.py
"""

import logging
import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "examples"))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import numpy as np

import gpn_multiphase_solver.grid.log_radial as lr
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from energy_balance import compute_balance

# После DEBT-063 функции нет — тогда один расчёт текущим кодом в оба столбца
ORIG = getattr(lr, "_cell_centers_mass", None)
DAY = 86400.0
T_SHUT = 15 * DAY
TERMS = [("delta_E", "ΔE"), ("cum_adiab", "адиабатический"), ("cum_deg", "дегазация"),
         ("cum_jt", "Джоуль–Томсон"), ("cum_conv", "конвекция"), ("cum_cond", "теплопроводность")]


def window(b, t0, t1):
    """Члены баланса за окно [t0, t1] — разность накопленных на концах."""
    i0 = int(np.argmin(np.abs(b["t"] - t0)))
    i1 = int(np.argmin(np.abs(b["t"] - t1)))
    assert abs(b["t"][i0] - t0) < 1 and abs(b["t"][i1] - t1) < 1, "нет записи на конце окна"
    return {k: b[k][i1] - b[k][i0] for k, _ in TERMS}


for name in ("16_well_shut_in", "17_shut_in_strong_cooling"):
    res = {}
    for mode in (("exp<ln r>", "√") if ORIG is not None else ("√",)):
        if ORIG is not None:
            lr._cell_centers_mass = ORIG if mode == "exp<ln r>" else (lambda a, b: np.sqrt(a * b))
        try:
            cfg = load_config(SOLVER / "examples" / name / "config.json")
            sim, init = SimulatorFactory.from_config(cfg)
            logging.disable(logging.INFO)
            h = sim.run(init)
            logging.disable(logging.NOTSET)
        finally:
            if ORIG is not None:
                lr._cell_centers_mass = ORIG
        b = compute_balance(h, None, None)
        res[mode] = (window(b, T_SHUT, T_SHUT + DAY), window(b, T_SHUT, b["t"][-1]))
    res.setdefault("exp<ln r>", res["√"])     # после DEBT-063 — один столбец
    print(f"\n{name}: член | первые сутки останова: exp<ln r> → √ | весь останов: exp<ln r> → √")
    for k, label in TERMS:
        a1, a2 = res["exp<ln r>"]
        s1, s2 = res["√"]
        print(f"  {label:18s} {a1[k]:+.4e} → {s1[k]:+.4e}   {a2[k]:+.4e} → {s2[k]:+.4e}")
