"""Аудит VAL-005: почему сверка правой части d матрицы энергии падает на примере 18 (первый вызов, dt = 60 с).

Запуск из probes/impl/numerical_solver (копия apply_plan.py) или из numerical_solver/ с аргументом-конфигом:
    <python> ..\\..\\audit_matrix_d.py [config.json]
"""
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print("SOLVER =", SOLVER)
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER / "tests"))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from test_energy_matrix_examples import (  # noqa: E402
    RTOL, build_reference, _ref_cell_properties, _ref_ext_properties, _ref_convective,
    _ref_jt, _ref_adiabatic, _ref_degassing)

cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else SOLVER / "examples" / "18_prototype_input" / "config.json"
cfg = load_config(cfg_path)
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
calls = [0]

# Члены решателя: обёртки над методами TridiagEnergySolver запоминают последний результат
seen = {}
for meth in ("compute_jt", "compute_adiabatic", "compute_degassing"):
    orig = getattr(sim._energy, meth)

    def wrap(*args, _orig=orig, _name=meth, **kw):
        seen[_name] = _orig(*args, **kw)
        return seen[_name]
    setattr(sim._energy, meth, wrap)


class Stop(Exception):
    pass


def probe(a, b, c, d, dt, T_old, T_ref, hydro_result, state_prev, bc):
    ref_a, ref_b, ref_c, ref_d, d_scale = build_reference(
        sim._grid, sim._pvt, cfg.rock, hydro_result, state_prev, dt, bc, T_ref=T_ref, with_scale=True)
    d_err = np.abs(d - ref_d)
    d_lim = RTOL * (np.abs(ref_d) + d_scale)
    bad = np.nonzero(~(d_err <= d_lim))[0]
    st = hydro_result.state
    dp = st.p - state_prev.p
    print(f"вызов {calls[0]}, dt = {dt:g} с: ячеек вне допуска {bad.size}")
    for j in bad[:12]:
        print(f"  j={j:3d}: d={d[j]:+.3e} ref_d={ref_d[j]:+.3e} scale={d_scale[j]:.3e} "
              f"d_err={d_err[j]:.3e}  p-p_old={dp[j]:+.3e} Па  T_old-T_ref={T_old[j] - T_ref:+.3e}  "
              f"Sg={st.Sg[j]:.2e}  Rs-Rs_old={st.Rs[j] - state_prev.Rs[j]:+.3e}")
    # Члены эталона — теми же шагами, что build_reference
    N, pvt, rock = sim._grid.N, sim._pvt, cfg.rock
    props = _ref_cell_properties(pvt, rock, st.p, st.Sg, st.Rs, state_prev.T)
    ext = _ref_ext_properties(pvt, bc)
    Phi_o, Phi_g, _, _ = _ref_convective(hydro_result.Q_o, hydro_result.Q_g, props['rho_o'],
                                         props['rho_g'], props['c_p_o'], props['c_p_g'], N, ext)
    ref = {"compute_jt": _ref_jt(Phi_o, Phi_g, props['mu_JT_o'], props['mu_JT_g'],
                                 hydro_result.Q_o, hydro_result.Q_g, st.p, N, ext, hydro_result.p_wf),
           "compute_adiabatic": _ref_adiabatic(rock, props['So'], st.Sg, props['rho_o'], props['rho_g'],
                                               props['c_p_o'], props['c_p_g'], props['mu_JT_o'],
                                               props['mu_JT_g'], st.p, state_prev.p, dt),
           "compute_degassing": _ref_degassing(sim._grid, pvt, rock, props['So'], st.Sg, st.Rs,
                                               state_prev.Rs, props['Bo'], hydro_result.G_o,
                                               props['L'], dt, N, bc.Rs_ext)}
    for j in bad[:3]:
        for k in ref:
            print(f"    {k:18s} j={j}: решатель {seen[k][j]:+.3e}, эталон {ref[k][j]:+.3e}")
        print(f"    G_o[{j}], G_o[{j + 1}] = {hydro_result.G_o[j]:+.3e}, {hydro_result.G_o[j + 1]:+.3e}; "
              f"Rs[{j - 1}..{j + 1}] = {st.Rs[j - 1]:.15g}, {st.Rs[j]:.15g}, {st.Rs[j + 1]:.15g}; "
              f"Q_o[{j}], Q_o[{j + 1}] = {hydro_result.Q_o[j]:+.3e}, {hydro_result.Q_o[j + 1]:+.3e}")
    zero_scale = np.nonzero(d_scale == 0.0)[0]
    print(f"  ячеек с нулевым масштабом: {zero_scale.size} (с {zero_scale.min() if zero_scale.size else '-'}); "
          f"среди них d != 0: {np.count_nonzero(d[zero_scale])}")
    calls[0] += 1
    if calls[0] >= 2:
        raise Stop


sim._energy.matrix_probe = probe
try:
    sim.run(init)
except Stop:
    pass
