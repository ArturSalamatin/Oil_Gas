"""DEBT-075: диапазоны S_g, p, R_s принятых подшагов гидродинамики во всех примерах.

Вопрос плана: какой допуск нужен проверке 0 <= S_g <= 1 (и p > 0, R_s >= 0, конечность)
принятого состояния, чтобы на штатных примерах она не сработала ни разу.

Обёртка PrototypeHydroAdapter.solve записывает состояние каждого возврата без исключения —
это принятые подшаги: Simulator отвергает подшаг только по HydroConvergenceError внутри solve.
Файлы пакета и прототипа не меняются.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-075\\probes\\sg_range_scan.py [пример ...]
"""
import logging
import sys
import time
from pathlib import Path

import numpy as np

import gpn_multiphase_solver
import radial_blackoil
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.io.config import load_config

SOLVER = Path.cwd()
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
print(f"прототип: {Path(radial_blackoil.__file__).parent}", flush=True)

EXAMPLES = sorted(d.name for d in (SOLVER / "examples").iterdir()
                  if (d / "config.json").is_file())

# ── Сводка по принятым подшагам ──
STATS = {}
_orig_solve = PrototypeHydroAdapter.solve


def _reset():
    STATS.clear()
    STATS.update(
        n=0,
        sg_min=np.inf, sg_max=-np.inf,
        sg2_min=np.inf,          # min S_g двухфазных ячеек (regime == 1)
        sg1_absmax=0.0,          # max |S_g| однофазных (regime == 2): ждём 0
        n_sg_neg=0, n_sg_gt1=0,  # число значений S_g < 0, S_g > 1 (по ячейкам и подшагам)
        p_min=np.inf, rs_min=np.inf, rs1_min=np.inf, n_rs_neg=0,
        rs_neg_min=0.0,          # самое отрицательное R_s
        n_nonfinite=0)


def solve(self, state, dt, bc):
    res = _orig_solve(self, state, dt, bc)
    s = res.state
    two = s.regime == 1
    st = STATS
    st["n"] += 1
    st["sg_min"] = min(st["sg_min"], float(np.min(s.Sg)))
    st["sg_max"] = max(st["sg_max"], float(np.max(s.Sg)))
    if two.any():
        st["sg2_min"] = min(st["sg2_min"], float(np.min(s.Sg[two])))
    if (~two).any():
        st["sg1_absmax"] = max(st["sg1_absmax"], float(np.max(np.abs(s.Sg[~two]))))
        st["rs1_min"] = min(st["rs1_min"], float(np.min(s.Rs[~two])))
    st["n_sg_neg"] += int(np.count_nonzero(s.Sg < 0))
    st["n_sg_gt1"] += int(np.count_nonzero(s.Sg > 1))
    st["p_min"] = min(st["p_min"], float(np.min(s.p)))
    st["rs_min"] = min(st["rs_min"], float(np.min(s.Rs)))
    st["n_rs_neg"] += int(np.count_nonzero(s.Rs < 0))
    st["rs_neg_min"] = min(st["rs_neg_min"], float(np.min(s.Rs)))
    st["n_nonfinite"] += int(np.count_nonzero(~(np.isfinite(s.p) & np.isfinite(s.Sg)
                                                & np.isfinite(s.Rs))))
    return res


PrototypeHydroAdapter.solve = solve

names = sys.argv[1:] or EXAMPLES
print(f"примеров: {len(names)}\n", flush=True)
hdr = (f"{'пример':32s} {'подш.':>6s} {'min Sg':>11s} {'max Sg':>9s} {'min Sg(2ф)':>11s} "
       f"{'|Sg|(1ф)':>9s} {'Sg<0':>5s} {'Sg>1':>5s} {'min p, МПа':>10s} {'min Rs':>11s} "
       f"{'min Rs(1ф)':>11s} {'Rs<0':>5s} {'не кон.':>7s} {'с':>6s}")
print(hdr)
total = {"n_sg_neg": 0, "n_sg_gt1": 0, "n_rs_neg": 0, "n_nonfinite": 0}
worst = {"sg_min": np.inf, "sg_max": -np.inf, "rs_min": np.inf, "p_min": np.inf}
for name in names:
    _reset()
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    t0 = time.perf_counter()
    try:
        sim, s0 = SimulatorFactory.from_config(cfg)
        logging.getLogger("gpn_multiphase_solver").setLevel(logging.ERROR)
        sim.run(s0)
        status = ""
    except Exception as exc:  # noqa: BLE001 — проба: печать причины
        status = f"  ОТКАЗ {type(exc).__name__}: {str(exc)[:100]}"
    st = STATS
    print(f"{name:32s} {st['n']:6d} {st['sg_min']:11.3e} {st['sg_max']:9.6f} "
          f"{st['sg2_min']:11.3e} {st['sg1_absmax']:9.2e} {st['n_sg_neg']:5d} {st['n_sg_gt1']:5d} "
          f"{st['p_min'] / 1e6:10.4f} {st['rs_min']:11.3e} {st['rs1_min']:11.3e} "
          f"{st['n_rs_neg']:5d} {st['n_nonfinite']:7d} {time.perf_counter() - t0:6.1f}{status}",
          flush=True)
    for k in total:
        total[k] += st[k]
    worst["sg_min"] = min(worst["sg_min"], st["sg_min"])
    worst["sg_max"] = max(worst["sg_max"], st["sg_max"])
    worst["rs_min"] = min(worst["rs_min"], st["rs_min"])
    worst["p_min"] = min(worst["p_min"], st["p_min"])

print(f"\nвсего: S_g < 0 — {total['n_sg_neg']}, S_g > 1 — {total['n_sg_gt1']}, "
      f"R_s < 0 — {total['n_rs_neg']}, не конечных — {total['n_nonfinite']}")
print(f"крайние: min S_g = {worst['sg_min']:.6e}, max S_g = {worst['sg_max']:.6f}, "
      f"min R_s = {worst['rs_min']:.6e}, min p = {worst['p_min'] / 1e6:.4f} МПа")
