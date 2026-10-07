"""FEAT-024: итерации двухфазного Ньютона на первом шаге примера 14 (N = 50 / 100).

Копия _newton_fixed_active_set прототипа (та же логика: полный шаг,
линейный поиск делением пополам до 12 раз, принимается уменьшение нормы
невязки inf) с журналом: норма, принятый alpha, ячейка и уравнение с
максимальной невязкой, S_g и p в ней, число ячеек с S_g < S_gc.

Запуск (из numerical_solver рабочего дерева .worktrees/feat-024):
    python <этот файл> N dt_s
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("HydroSolverPrototype/Prototype_1.0.3").resolve()))
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport, BlackOilState  # noqa: E402

BAR = 1e5
N, dt = int(sys.argv[1]), float(sys.argv[2])
cfg = load_config(Path("examples/14_high_gor_cooling/config.json"))
cfg.grid.N = N
sim, init = SimulatorFactory.from_config(cfg)
m = sim._hydro._model
r = sim._grid.r_centers
m.set_bhp_control(6.0e6 / BAR)


def traced(z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
    n = m.grid.n
    z = np.asarray(z0, float).copy()
    scale = max(np.linalg.norm(m.residual(z, state_old, dt_s, gas_active), np.inf), 1e-9)
    two = int(gas_active.sum())
    print(f"\n  Ньютон: активных {two}")
    for it in range(1, max_iter + 1):
        J, f = m.finite_difference_jacobian(z, state_old, dt_s, gas_active)
        nrm = np.linalg.norm(f, np.inf)
        k = int(np.argmax(np.abs(f)))
        cell, eq = k % n, ("нефть" if k < n else "газ")
        sg = z[n:][gas_active]
        print(f"   it {it:2d}: |F| {nrm:.3e}  макс: ячейка {cell:3d} ({r[cell]:7.3f} м, {eq}), "
              f"p {z[cell] / 10:6.3f} МПа, S_g {z[n + cell] if gas_active[cell] else 0.0:.4f};  "
              f"S_g<0.1: {int((sg < 0.1).sum())}, S_g max {sg.max() if sg.size else 0:.3f}", end="")
        if nrm <= atol_sm3s + rtol * scale:
            print("  → сошёлся")
            return z, BlackOilNewtonReport(True, it - 1, float(nrm))
        dz = m._linear_solve(J, -f)
        alpha, accepted = 1.0, False
        for _ in range(12):
            trial = z + alpha * dz
            if m._trial_is_reasonable(trial, gas_active):
                if np.linalg.norm(m.residual(trial, state_old, dt_s, gas_active), np.inf) < nrm:
                    z, accepted = trial, True
                    break
            alpha *= 0.5
        print(f"  alpha {alpha if accepted else 0:.2e}")
        if not accepted:
            # Где полный шаг Ньютона наиболее агрессивен
            dsg = dz[n:][gas_active]
            idx = np.where(gas_active)[0]
            j = idx[int(np.argmax(np.abs(dsg)))] if dsg.size else -1
            print(f"   линейный поиск исчерпан: max|dS_g| = {np.abs(dsg).max():.3f} в ячейке {j} "
                  f"({r[j]:.3f} м), max|dp| = {np.abs(dz[:n]).max() / 10:.3f} МПа")
            return z, BlackOilNewtonReport(False, it, float(nrm))
    f = m.residual(z, state_old, dt_s, gas_active)
    return z, BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)))


m._newton_fixed_active_set = traced
s0 = BlackOilState(pressure_bar=init.p / BAR, rs_sm3_sm3=init.Rs.copy(),
                   sg=init.Sg.copy(), gas_active=(init.regime == 1))
print(f"N = {N}, dt = {dt:g} с, первая ячейка r = {r[0]:.4f} м")
# Только исходный алгоритм: запасной путь даёт тот же тупик (fine_grid_first_step.py)
new, rep = m._advance_phases(s0, dt)
print(f"\nитог: сошёлся {rep.converged}")
