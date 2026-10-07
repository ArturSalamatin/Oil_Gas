"""DEBT-043, план: граница округления на укороченных сценариях тестов и намеренно воспроизведённый дефект BUG-007.

Сценарии — как _run_balance в tests/test_energy_balance_examples.py
(6 ч одним интервалом, N = 25). Для каждого: относительная невязка,
граница округления B = Σ_подшаги ε·Σ_j (ρc)_j V_j T_j и |невязка|/B.

Дефект BUG-007: конвективный член накопителя на слое T^n вместо T^{n+1}
(вклад подшага пересчитан по T_prev). Ожидание — |невязка|/B ≫ 1.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\plan_short_runs.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = (HERE.parents[3] / "numerical_solver").resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

EPS = float(np.finfo(float).eps)
ORIG = EnergyBalanceAccumulator.add_accumulation


def run(example, p_wf=None, defect=False):
    cfg = load_config(SOLVER / "examples" / example / "config.json")
    cfg.grid.N = 25
    cfg.time.history = cfg.time.history[:1]
    cfg.time.history[0].dt = 21600.0
    cfg.output.log_level = "WARNING"
    if p_wf is not None:
        cfg.time.history[0].p_wf = p_wf
    sim, init = SimulatorFactory.from_config(cfg)
    V = sim._grid.volumes
    B = {"v": 0.0, "n": 0}

    def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
        # Коэффициенты подшага гасятся внутри исходного метода — берём до вызова
        Pp, Pm, dts, Text = self._Phi_plus, self._Phi_minus, self._dt_substep, self._T_ext
        conv0 = self.cum_conv
        ORIG(self, T_new, T_prev, rho_cp_eff, dt)
        if defect:
            # BUG-007: F_j по T^n (T_prev) вместо T^{n+1}
            N = len(T_prev)
            TL = np.concatenate(([T_prev[0]], T_prev[:-1]))
            TR = np.concatenate((T_prev[1:], [Text]))
            F = Pp[0:N] * (T_prev - TL) + Pm[1:N + 1] * (TR - T_prev)
            self.cum_conv = conv0 - float(np.sum(F)) * dts
        B["v"] += EPS * float(np.sum(rho_cp_eff * V * T_new))
        B["n"] += 1

    EnergyBalanceAccumulator.add_accumulation = add_accumulation
    try:
        h = sim.run(init)
    finally:
        EnergyBalanceAccumulator.add_accumulation = ORIG
    bal = compute_balance(h, sim._grid, cfg)
    res = float(bal["residual"][-1])
    print(f"  {example:22s} p_wf={str(p_wf):7s} дефект={str(defect):5s} | подшагов {B['n']:3d} | "
          f"отн. {float(bal['rel_residual'][-1]):.2e} | |невязка| {abs(res):.2e} Дж | "
          f"B {B['v']:.2e} Дж | |невязка|/B {abs(res) / B['v']:.3e}", flush=True)


for ex, pwf in (("03_standing_corey", None), ("04_table_table", None), ("04_table_table", 16e6)):
    run(ex, pwf)
for ex in ("03_standing_corey", "04_table_table"):
    run(ex, defect=True)
