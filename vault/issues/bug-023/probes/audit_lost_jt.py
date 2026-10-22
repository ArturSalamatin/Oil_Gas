r"""Аудит BUG-023: сколько JT-вклада левой грани теряет текущий эталон на 16 и 17 и как это соотносится с допуском.

audit_phi_plus.py нашёл у 16 и 17 (останов) грани с Q_o > 0 — течение от скважины. Здесь на каждом
вызове energy.solve: потерянный вклад ΔJ_j = Σ_α μ_JT,α^{j-1/2}·Φ⁺_{α,j-1/2}·(p_j − p_{j-1})
по внутренним граням (свойства — те же функции эталона теста) и отношение |ΔJ| к допуску сверки d
RTOL·(|d_ref| + масштаб) текущего эталона. Запуск из numerical_solver/:
    .venv\Scripts\python ..\vault\issues\bug-023\probes\audit_lost_jt.py [пример ...]
"""
import sys
from pathlib import Path

import numpy as np

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, не из {SOLVER}")
print("SOLVER =", SOLVER)
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER / "tests"))

import test_energy_matrix_examples as tme  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

examples = sys.argv[1:] or ["16_well_shut_in", "17_shut_in_strong_cooling"]
print(f"{'пример':28s} {'вызовов':>7s} {'с ΔJ≠0':>7s} {'max |ΔJ|, Вт':>13s} {'max |ΔJ|/допуск':>16s}")
for example in examples:
    cfg = load_config(tme.EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)
    s = {"calls": 0, "hit": 0, "dJ": 0.0, "ratio": 0.0}

    def probe(a, b, c, d, dt, T_old, T_ref, hydro_result, state_prev, bc, s=s):
        s["calls"] += 1
        st = hydro_result.state
        N = simulator._grid.N
        props = tme._ref_cell_properties(simulator._pvt, cfg.rock, st.p, st.Sg, st.Rs, state_prev.T)
        ext = tme._ref_ext_properties(simulator._pvt, bc)
        Phi_o, Phi_g, _, _ = tme._ref_convective(hydro_result.Q_o, hydro_result.Q_g,
                                                 props['rho_o'], props['rho_g'],
                                                 props['c_p_o'], props['c_p_g'], N, ext)
        # Потерянное слагаемое — левая грань внутренних граней f = 1..N-1 (ячейка j = f)
        dJ = np.zeros(N)
        for f in range(1, N):
            dp = st.p[f] - st.p[f - 1]
            for Phi, Q, mu in ((Phi_o, hydro_result.Q_o, props['mu_JT_o']),
                               (Phi_g, hydro_result.Q_g, props['mu_JT_g'])):
                if Phi[f] > 0.0:
                    dJ[f] += mu[tme._upstream(Q[f], f)] * Phi[f] * dp
        if not dJ.any():
            return
        s["hit"] += 1
        _, _, _, ref_d, scale = tme.build_reference(
            simulator._grid, simulator._pvt, cfg.rock, hydro_result, state_prev, dt, bc,
            T_ref=T_ref, with_scale=True)
        lim = tme.RTOL * (np.abs(ref_d) + scale)
        s["dJ"] = max(s["dJ"], float(np.max(np.abs(dJ))))
        s["ratio"] = max(s["ratio"], float(np.max(np.abs(dJ) / lim)))

    simulator._energy.matrix_probe = probe
    simulator.run(initial)
    print(f"{example:28s} {s['calls']:7d} {s['hit']:7d} {s['dJ']:13.2e} {s['ratio']:16.2e}", flush=True)
