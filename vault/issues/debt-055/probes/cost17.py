"""DEBT-055, проба планирования: цена условия ячейки на примере 17 при другой сетке.

Пример 17 с заменёнными R_ext, N и порогом newton_cell_tol; полный расчёт (30 сут).
Считаются: время, якобианы, вызовы advance и их отказы, отказы адаптера (подшаги,
которые Simulator дробит) и среди них — «только условие по ячейке» (текст DEBT-054).

Предсказания гипотез о полу меры ячеек (floor_probe.py):
  V (оценка реестра, eps_маш*(R_ext/r_w)^2): R_ext = 2000 м при 1e-8 — порог в 8 раз ниже
    пола, расчёт дорожает, как пример 17 при 1e-10 (якобианы x2.9); N = 800 — как N = 200;
  Q (квантование давления, пол ~ dt*N^2/ln^2(R_ext/r_w)): R_ext = 2000 м — пол ниже, чем у 17,
    цены нет; N = 800 — пол x16 к N = 200 (~1e-8 на останове при dt = 3600 с), расчёт дорожает.

Аргументы: R_ext N eps|none [тег]. Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-055\\probes\\cost17.py 2000 200 1e-8
"""
import sys
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
HERE = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory          # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config             # noqa: E402

rext, N, eps = float(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
tag = f"R{rext:g}_N{N}_{eps}"
OUT = open(HERE / f"cost17_{tag}.out.txt", "w", encoding="utf-8")


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


cfg = load_config(SOLVER / "examples" / "17_shut_in_strong_cooling" / "config.json")
cfg.output.log_level = "ERROR"
cfg.geometry.R_ext = rext
cfg.grid.N = N
cfg.numerics.newton_cell_tol = None if eps == "none" else float(eps)
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
pv = model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, np.full(N, cfg.initial_conditions.p0 / 1e5))
out(f"SOLVER = {SOLVER}; R_ext = {rext:g} м, N = {N}, newton_cell_tol = {model.cell_tol}; "
    f"V_max/V_min = {pv.max() / pv.min():.3e}, eps_маш*V_max/V_min = {np.finfo(float).eps * pv.max() / pv.min():.2e}")

cnt = {"jac": 0, "adv": 0, "adv_fail": 0}
jac0, adv0, adv4 = model.finite_difference_jacobian, model.advance, model.advance_fourth_stage


def jac(*a, **k):
    cnt["jac"] += 1
    return jac0(*a, **k)


def advance(*a, **k):
    new, rep = adv0(*a, **k)
    cnt["adv"] += 1
    cnt["adv_fail"] += not rep.converged
    return new, rep


def advance4(*a, **k):
    new, rep = adv4(*a, **k)
    cnt["adv"] += 1
    cnt["adv_fail"] += not rep.converged
    return new, rep


model.finite_difference_jacobian, model.advance, model.advance_fourth_stage = jac, advance, advance4
fails = []
solve0 = sim._hydro.solve


def solve(state, dt, bc):
    try:
        return solve0(state, dt, bc)
    except HydroConvergenceError as e:
        fails.append(str(e))
        raise


sim._hydro.solve = solve
t0 = time.perf_counter()
try:
    hist = sim.run(init)
    rs = np.array([s.Rs[0] for s in hist.states])
    d = np.diff(rs[16:])
    res = f"прошёл; R_s(r_w) конец {rs[-1]:.5f}, min dR_s на останове {d.min():+.2e}"
except RuntimeError as e:
    res = f"ОТКАЗ РАСЧЁТА: {str(e)[:200]}"
cell_only = sum("только условие по ячейке" in s for s in fails)
out(f"{tag}: {res}")
out(f"  время {time.perf_counter() - t0:.0f} с, якобианов {cnt['jac']}, advance {cnt['adv']} "
    f"(отказов {cnt['adv_fail']}), отказов адаптера {len(fails)}, из них «только ячейка» {cell_only}")
