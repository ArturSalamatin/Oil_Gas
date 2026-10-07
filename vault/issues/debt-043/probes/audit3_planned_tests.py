"""DEBT-043, аудит плана (вариант Б): тела новых и изменённых тестов шагов 1–2 с кодом шага 1.

solve подменён кодом из файла плана (audit3_planned_solve.install). Исполняются:
  [2.1] TestDeviationForm::test_solution_matches_absolute_form — по тексту плана;
  [2.2] test_energy_balance_machine_precision[03, 04] — по тексту плана;
  [1.5] test_matrix_matches_reference с эталоном, сдвинутым на T_ref (build_reference
        с параметром T_ref, проба с аргументом T_ref) — на 03, 10, 16, 20.

Запуск (из numerical_solver/):
    $env:PYTHONPATH = "D:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-043\\probes"
    .venv\\Scripts\\python D:\\...\\audit3_planned_tests.py
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = (HERE.parents[3] / "numerical_solver").resolve()
for p in (SOLVER, SOLVER / "tests", SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import audit3_planned_solve  # noqa: E402
audit3_planned_solve.install()

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402
from gpn_multiphase_solver.fluxes import compute_fluxes  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, SOLVER / "tests" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


te = load("test_energy")
tbe = load("test_energy_balance_examples")
tme = load("test_energy_matrix_examples")

# ── [2.1] TestDeviationForm — тело по плану ──
N = te.N
grid = LogRadialGrid(te.R_WELL, te.R_EXT, te.H, N, te.K_PERM)
pvt = te._make_pvt(mu_JT_oil=-4e-7)
rp = CoreyRP(0.2, 0.05, 2.0, 2.0)
solver = TridiagEnergySolver(grid, pvt, te._rock())
p = te._log_pressure_profile(grid, te.P_WF, te.P0)
state = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, te.RS0), T=np.full(N, 345.0),
                        regime=np.full(N, 2, dtype=int), t=0.0)
bc = te._bc(350.0)
hydro = compute_fluxes(state, grid, pvt, rp, bc)
state_prev = SimulationState(p=p.copy(), Sg=np.zeros(N), Rs=np.full(N, te.RS0),
                             T=np.full(N, 345.0), regime=np.full(N, 2, dtype=int), t=0.0)
captured = {}
solver.matrix_probe = lambda **kw: captured.update(kw)
T_new = solver.solve(hydro, state_prev, te.DT, te._bc(350.0))
a, b, c, d, T_ref = (captured[k] for k in ("a", "b", "c", "d", "T_ref"))
A1 = b * T_ref
A1[1:] += a[1:] * T_ref
A1[:-1] += c[:-1] * T_ref
T_abs = solver.solve_banded_system(a, b, c, d + A1, N)
dev = float(np.max(np.abs(T_new - T_abs)))
print(f"[2.1] T_ref = {T_ref}; max|T_new − T_abs| = {dev:.2e} K (< 1e-9: {dev < 1e-9}); "
      f"max|T_new − T_ref| = {np.max(np.abs(T_new - T_ref)):.3f} K (> 1: {np.max(np.abs(T_new - T_ref)) > 1.0})")
# Приток через контур ≠ 0 — граничная строка (Φ⁻_N·T_ext в d) нагружена, и
# неверный сдвиг T_ext тест бы заметил
print(f"      Q_o на контуре = {captured['hydro_result'].Q_o[-1]:.3e} м³/с (< 0 — приток)")

# ── [2.2] страж машинного уровня ──
for ex in ("03_standing_corey", "04_table_table"):
    bal = tbe._run_balance(ex)
    rel = abs(float(bal["rel_residual"][-1]))
    print(f"[2.2] {ex}: rel {rel:.2e} (< 1e-14: {rel < 1e-14})")

# ── [1.5] сверка матрицы с эталоном, сдвинутым на T_ref ──
def build_reference_shifted(grid, pvt, rock, hydro_result, state_prev, dt, bc, T_ref=0.0,
                            with_scale=False):
    """Копия build_reference (test_energy_matrix_examples.py:615-669) с правкой шага 1.5 плана."""
    Nn = grid.N
    st = hydro_result.state
    props = tme._ref_cell_properties(pvt, rock, st.p, st.Sg, st.Rs, state_prev.T)
    ext = tme._ref_ext_properties(pvt, bc)
    Phi_o, Phi_g, Phi_plus, Phi_minus = tme._ref_convective(
        hydro_result.Q_o, hydro_result.Q_g, props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'], Nn, ext)
    Q_T_internal, Q_T_ext = tme._ref_conductive(grid, props['lambda_eff'])
    p_wf = hydro_result.p_wf
    J_jt = tme._ref_jt(Phi_o, Phi_g, props['mu_JT_o'], props['mu_JT_g'],
                       hydro_result.Q_o, hydro_result.Q_g, st.p, Nn, ext, p_wf)
    Q_ad = tme._ref_adiabatic(rock, props['So'], st.Sg, props['rho_o'], props['rho_g'],
                              props['c_p_o'], props['c_p_g'], props['mu_JT_o'], props['mu_JT_g'],
                              st.p, state_prev.p, dt)
    Q_deg = tme._ref_degassing(grid, pvt, rock, props['So'], st.Sg, st.Rs, state_prev.Rs,
                               props['Bo'], hydro_result.G_o, props['L'], dt, Nn, bc.Rs_ext)
    abcd = tme._ref_assemble(grid, Nn, dt, state_prev.T - T_ref, bc.T_ext - T_ref,
                             props['rho_cp_eff'], Q_T_internal, Q_T_ext,
                             Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)
    if not with_scale:
        return abcd
    d_scale = tme._ref_d_scale(grid, Nn, dt, state_prev.T - T_ref, bc.T_ext - T_ref,
                               props['rho_cp_eff'], Q_T_ext, Phi_minus, J_jt, Q_ad, Q_deg)
    return (*abcd, d_scale)


for ex in ("03_standing_corey", "10_deep_degassing", "16_well_shut_in", "20_rs300_cooling"):
    cfg = load_config(SOLVER / "examples" / ex / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    st = dict(n=0, worst=0.0, a_ok=True)

    def probe(a, b, c, d, dt, T_old, T_ref, hydro_result, state_prev, bc):
        ra, rb, rc, rd, ds = build_reference_shifted(sim._grid, sim._pvt, cfg.rock, hydro_result,
                                                     state_prev, dt, bc, T_ref=T_ref, with_scale=True)
        for x, y in ((a, ra), (b, rb), (c, rc)):
            np.testing.assert_allclose(x, y, rtol=tme.RTOL, atol=0.0)
        lim = tme.RTOL * (np.abs(rd) + ds)
        st["worst"] = max(st["worst"], float(np.max(np.abs(d - rd) / lim)))
        st["a_ok"] &= (a[0] == 0.0 and c[-1] == 0.0)
        st["n"] += 1

    sim._energy.matrix_probe = probe
    sim.run(init)
    print(f"[1.5] {ex}: вызовов {st['n']}, max |d − d_ref|/допуск = {st['worst']:.2e} "
          f"(≤ 1: {st['worst'] <= 1.0}), a[0] = c[N-1] = 0: {st['a_ok']}", flush=True)
