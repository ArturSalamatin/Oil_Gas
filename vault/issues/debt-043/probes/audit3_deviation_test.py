"""DEBT-043, аудит плана: ловит ли TestDeviationForm неверный сдвиг — прежнее и исправленное тело.

Прежнее тело (по пробе: d + A·T_ref) проверяет только согласованность solve со своей d.
Исправленное — перехватывает аргументы assemble_tridiag и собирает абсолютную форму
заново по абсолютным T^n, T_ext с теми же коэффициентами.

Контроль: реализация с ошибкой — T_ext не сдвинут (theta_ext = T_ext).

Запуск (из numerical_solver/):
    $env:PYTHONPATH = "D:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-043\\probes"
    .venv\\Scripts\\python D:\\...\\audit3_deviation_test.py
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = (HERE.parents[3] / "numerical_solver").resolve()
for p in (SOLVER, SOLVER / "tests", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import audit3_planned_solve as aps  # noqa: E402
import gpn_multiphase_solver.energy.tridiag as tri  # noqa: E402
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402
from gpn_multiphase_solver.fluxes import compute_fluxes  # noqa: E402

spec = importlib.util.spec_from_file_location("te", SOLVER / "tests" / "test_energy.py")
te = importlib.util.module_from_spec(spec)
spec.loader.exec_module(te)


def install(source):
    ns = dict(vars(tri))
    exec(compile(source, "<solve>", "exec"), ns)
    tri.TridiagEnergySolver.solve = ns["solve"]


def setup():
    N = te.N
    grid = LogRadialGrid(te.R_WELL, te.R_EXT, te.H, N, te.K_PERM)
    pvt = te._make_pvt(mu_JT_oil=-4e-7)
    solver = tri.TridiagEnergySolver(grid, pvt, te._rock())
    p = te._log_pressure_profile(grid, te.P_WF, te.P0)
    st = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, te.RS0), T=np.full(N, 345.0),
                         regime=np.full(N, 2, dtype=int), t=0.0)
    hydro = compute_fluxes(st, grid, pvt, CoreyRP(0.2, 0.05, 2.0, 2.0), te._bc(350.0))
    prev = SimulationState(p=p.copy(), Sg=np.zeros(N), Rs=np.full(N, te.RS0),
                           T=np.full(N, 345.0), regime=np.full(N, 2, dtype=int), t=0.0)
    return N, solver, hydro, prev


def old_body():
    N, solver, hydro, prev = setup()
    cap = {}
    solver.matrix_probe = lambda **kw: cap.update(kw)
    T_new = solver.solve(hydro, prev, te.DT, te._bc(350.0))
    a, b, c, d, T_ref = (cap[k] for k in ("a", "b", "c", "d", "T_ref"))
    A1 = b * T_ref
    A1[1:] += a[1:] * T_ref
    A1[:-1] += c[:-1] * T_ref
    T_abs = solver.solve_banded_system(a, b, c, d + A1, N)
    return float(np.max(np.abs(T_new - T_abs)))


def new_body():
    N, solver, hydro, prev = setup()
    calls = []
    orig = solver.assemble_tridiag

    def spy(N_, dt_, T_old_, T_ext_, *coef):
        calls.append((np.array(T_old_, copy=True), T_ext_, coef))
        return orig(N_, dt_, T_old_, T_ext_, *coef)

    solver.assemble_tridiag = spy
    T_new = solver.solve(hydro, prev, te.DT, te._bc(350.0))
    theta_old, theta_ext, coef = calls[0]
    a, b, c, d_abs = orig(N, te.DT, prev.T, 350.0, *coef)
    T_abs = solver.solve_banded_system(a, b, c, d_abs, N)
    return (theta_ext == 0.0, bool(np.array_equal(theta_old, prev.T - 350.0)),
            float(np.max(np.abs(T_new - T_abs))))


good = aps.planned_source()
bad = good.replace("theta_ext = T_ext - T_ref    # = 0.0", "theta_ext = T_ext")
assert bad != good

for label, src in (("код плана", good), ("ошибка: T_ext не сдвинут", bad)):
    install(src)
    dev_old = old_body()
    ext_ok, old_ok, dev_new = new_body()
    print(f"{label}:\n  прежнее тело: max|T_new − T_abs| = {dev_old:.2e} K → "
          f"{'проходит' if dev_old < 1e-9 else 'ПАДАЕТ'}\n"
          f"  исправленное: θ_ext == 0 {ext_ok}, θ_old == T_old − 350 {old_ok}, "
          f"max|T_new − T_abs| = {dev_new:.2e} K → "
          f"{'проходит' if (ext_ok and old_ok and dev_new < 1e-9) else 'ПАДАЕТ'}")
