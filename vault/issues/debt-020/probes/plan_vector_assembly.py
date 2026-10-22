"""DEBT-020, план: векторная сборка с единым Q_T[N+1] побитово равна нынешней.

Код ядра не меняется. На время прогона TridiagEnergySolver.assemble_tridiag и
compute_conductive_transmissibility подменяются обёртками: обёртка зовёт
нынешний метод, затем кандидатную реализацию плана (функции ниже) и сравнивает
результаты ПО БАЙТАМ (tobytes: различает и знак нуля). Расхождение — исключение
с номером вызова.

Две части:
  synth   — синтетика N = 1, 2, 3, 10: случайные коэффициенты, T_ext != 0,
            Phi_plus[0] > 0 (ветвь, которой на рабочем пути нет), λ = 0.
  examples — штатные конфиги примеров целиком (каждый вызов solve).

Запуск (из numerical_solver основного каталога или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-020\\probes\\plan_vector_assembly.py synth
    .venv\\Scripts\\python ..\\vault\\issues\\debt-020\\probes\\plan_vector_assembly.py examples 07_degassing_adiabatic_only 10_deep_degassing
"""

import sys
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), \
    f"запускать из numerical_solver, а не из {SOLVER}"
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

from gpn_multiphase_solver import factory  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

print(f"Код: {factory.__file__}")

ORIG_COND = TridiagEnergySolver.compute_conductive_transmissibility
ORIG_ASM = TridiagEnergySolver.assemble_tridiag


# ── Кандидаты плана ──

def new_conductive(self, lambda_eff, N):
    """Q_T [N+1]: Q_T[0] = 0 (Нейман), Q_T[1..N-1] внутренние, Q_T[N] контур."""
    grid = self._grid
    Q_T = np.zeros(N + 1)
    w_L = grid.log_weights_left
    w_R = grid.log_weights_right
    lam_L = lambda_eff[:-1]
    lam_R = lambda_eff[1:]
    with np.errstate(divide='ignore'):
        R_series = w_L / lam_L + w_R / lam_R
        Q_T[1:N] = 2.0 * np.pi * grid.h / R_series
    geom_ext = 2.0 * np.pi * grid.h / np.log(grid.R_ext / grid.r_centers[-1])
    Q_T[N] = geom_ext * lambda_eff[-1]
    return Q_T


def new_assemble(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T,
                 Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
    """Сборка по eq:tridiag_a…d на всех строках; порядок сложений — как в цикле."""
    V = self._grid.volumes
    cap = V * rho_cp_eff / dt

    a = -Q_T[:-1] - Phi_plus[:-1]
    a[0] = 0.0
    c = -Q_T[1:] + Phi_minus[1:]
    c[N - 1] = 0.0

    b = cap + Q_T[:-1]
    b += Q_T[1:]
    b[1:] += Phi_plus[1:N]
    b -= Phi_minus[1:]

    d = cap * T_old + J_jt + V * (Q_ad + Q_deg)
    d[N - 1] = (cap[N - 1] * T_old[N - 1]
                + Q_T[N] * T_ext
                + (-Phi_minus[N]) * T_ext
                + J_jt[N - 1]
                + V[N - 1] * (Q_ad[N - 1] + Q_deg[N - 1]))
    return a, b, c, d


def _same(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return x.shape == y.shape and x.tobytes() == y.tobytes()


def _to_full(Q_T_internal, Q_T_ext, N):
    Q_T = np.zeros(N + 1)
    Q_T[1:N] = Q_T_internal
    Q_T[N] = Q_T_ext
    return Q_T


calls = {"cond": 0, "asm": 0}


def wrapped_cond(self, lambda_eff, N):
    Q_int, Q_ext = ORIG_COND(self, lambda_eff, N)
    Q_T = new_conductive(self, lambda_eff, N)
    if not (Q_T[0] == 0.0 and _same(Q_T[1:N], Q_int) and _same(Q_T[N], Q_ext)):
        raise AssertionError(f"Q_T расходится, вызов {calls['cond']}, N = {N}")
    calls["cond"] += 1
    return Q_int, Q_ext


def wrapped_asm(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
                Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
    old = ORIG_ASM(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal,
                   Q_T_ext, Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)
    new = new_assemble(self, N, dt, T_old, T_ext, rho_cp_eff,
                       _to_full(Q_T_internal, Q_T_ext, N),
                       Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)
    for name, x, y in zip("abcd", old, new):
        if not _same(x, y):
            j = int(np.flatnonzero(x != y)[0]) if x.shape == y.shape else -1
            raise AssertionError(
                f"{name} расходится, вызов {calls['asm']}, N = {N}, ячейка {j}: "
                f"{x[j]!r} против {y[j]!r}")
    calls["asm"] += 1
    return old


def synth():
    rng = np.random.default_rng(20261011)
    n_cases = 0
    for N in (1, 2, 3, 10):
        grid = LogRadialGrid(0.1, 200.0, 10.0, N, 1e-13)
        solver = TridiagEnergySolver(grid, None, None)
        for trial in range(200):
            lam = rng.uniform(0.2, 3.0, N)
            if trial % 10 == 0:
                lam[:] = 0.0                     # конфиг без теплопроводности
            wrapped_cond(solver, lam, N)
            Q_int, Q_ext = ORIG_COND(solver, lam, N)
            Phi = rng.normal(0.0, 300.0, N + 1)
            Phi_plus = np.maximum(Phi, 0.0)
            Phi_minus = np.minimum(Phi, 0.0)
            Phi_plus[0] = abs(rng.normal(0.0, 300.0))   # втекание через забой
            wrapped_asm(solver, N, rng.uniform(1.0, 86400.0),
                        rng.uniform(300.0, 360.0, N), rng.uniform(300.0, 360.0),
                        rng.uniform(1e6, 3e6, N), Q_int, Q_ext,
                        Phi_plus, Phi_minus,
                        rng.normal(0.0, 50.0, N), rng.normal(0.0, 1.0, N),
                        rng.normal(0.0, 1.0, N))
            n_cases += 1
    print(f"synth: {n_cases} случаев, N = 1, 2, 3, 10 — побитово OK")


def examples(names):
    TridiagEnergySolver.compute_conductive_transmissibility = wrapped_cond
    TridiagEnergySolver.assemble_tridiag = wrapped_asm
    from gpn_multiphase_solver.factory import SimulatorFactory
    for name in names:
        calls["cond"] = calls["asm"] = 0
        t0 = time.perf_counter()
        cfg = load_config(SOLVER / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        sim.run(init)
        print(f"  {name}: N = {sim._grid.N}, вызовов сборки {calls['asm']}, "
              f"побитово OK, {time.perf_counter() - t0:.1f} с")


if __name__ == "__main__":
    if sys.argv[1] == "synth":
        synth()
    else:
        examples(sys.argv[2:])
