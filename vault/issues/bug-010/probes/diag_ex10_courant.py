"""Что особенного в шаге 450 с у примера 10?

Проверяем, не теряет ли трёхдиагональная матрица диагональное преобладание.
Схема неявная и безусловно устойчива ПО КОНДУКЦИИ, но конвективные Phi
входят в диагональ b и внедиагональные a, c. При противопотоке всё
корректно, но если знак Phi на грани таков, что вклад уходит не в ту
сторону, диагональ может ослабнуть.

Считаем на каждом тепловом шаге: min(|b| - |a| - |c|) по строкам.
"""
import sys
from pathlib import Path

ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
for p in (str(ROOT), str(ROOT / "examples"),
          str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

stat = {}
_orig = TridiagEnergySolver.assemble_tridiag


def patched(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
            Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
    a, b, c, d = _orig(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal,
                       Q_T_ext, Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)
    dom = np.abs(b) - np.abs(a) - np.abs(c)
    stat.setdefault("dom_min", []).append(float(np.min(dom)))
    stat.setdefault("b_min", []).append(float(np.min(np.abs(b))))
    # вклад накопления против конвекции: cap = V rho_cp/dt
    cap = self._grid.volumes * rho_cp_eff / dt
    conv_scale = np.abs(Phi_plus[1:]) + np.abs(Phi_minus[:-1])
    stat.setdefault("cap_over_conv", []).append(
        float(np.min(cap / np.maximum(conv_scale, 1e-30))))
    return a, b, c, d


def run_first(dt):
    stat.clear()
    cfg = load_config(ROOT / "examples" / "10_deep_degassing" / "config.json")
    cfg.output.log_level = "WARNING"
    cfg.time.dt_integration = dt
    cfg.time.history = cfg.time.history[:1]
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    return np.array(hist.states[-1].T, float), dict(stat)


TridiagEnergySolver.assemble_tridiag = patched
try:
    T_ref, _ = run_first(50.0)
    print(f"{'dt':>8s} {'max|dT|':>12s} {'min(|b|-|a|-|c|)':>18s} "
          f"{'min cap/conv':>14s}")
    for dt in (600.0, 450.0, 400.0, 360.0):
        T, st = run_first(dt)
        e = float(np.max(np.abs(T - T_ref)))
        print(f"{dt:8.0f} {e:12.4e} {min(st['dom_min']):18.4e} "
              f"{min(st['cap_over_conv']):14.4e}")
finally:
    TridiagEnergySolver.assemble_tridiag = _orig
