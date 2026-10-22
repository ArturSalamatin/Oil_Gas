"""DEBT-043, план (вариант Б): СЛАУ температуры в отклонениях θ = T − T_ref, T_ref = T_ext подшага.

Будущий код tridiag.solve исполняется подменой в памяти, рабочие файлы не меняются:
  - assemble_tridiag получает T_old − T_ref и T_ext − T_ref (= 0): правая часть сразу в θ;
  - solve_banded_system даёт θ^{n+1}; решатель возвращает T^{n+1} = θ^{n+1} + T_ref;
  - накопитель получает T_ext − T_ref в add_substep и θ^{n+1}, θ^n в add_accumulation.
Накопитель инвариантен к общему сдвигу температур (все члены — разности или от T
не зависят), поэтому его формулы не меняются.

Для каждого примера: относительная невязка сейчас и в θ, максимум по записям,
отличие финальных полей T, p, Sg от нынешнего расчёта.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\plan2_theta_emulation.py [пример ...]
    $env:DEBT043_SOLVER = "<дерево>\\numerical_solver"   # другое дерево (worktree BUG-020)
    $env:DEBT043_DT = "360"                              # шаг интегрирования вместо конфига
    $env:DEBT043_SHORT = "1"                             # укороченные сценарии тестов (6 ч, N = 25)
"""

import copy
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path(os.environ.get("DEBT043_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

ALL = ["01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey", "04_table_table",
       "04a_high_gas_saturation", "05_standing_table_rp", "06_table_corey_rp",
       "07_degassing_adiabatic_only", "08_degassing_jt", "09_degassing_latent_heat",
       "10_deep_degassing", "11_degassing_at_boundary", "12_large_drainage_radius",
       "13a_pwf_ramp_down", "13b_pwf_alternating", "14_high_gor_cooling",
       "15_oil_rate_ramp_up", "16_well_shut_in", "19_rs150_cooling", "20_rs300_cooling",
       "21_rs100_cooling"]

_SUB0 = EnergyBalanceAccumulator.add_substep
_ACC0 = EnergyBalanceAccumulator.add_accumulation


def config(name, short_pwf=None):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    if os.environ.get("DEBT043_DT"):
        cfg.time.dt_integration = float(os.environ["DEBT043_DT"])
    if os.environ.get("DEBT043_SHORT"):
        cfg.grid.N = 25
        cfg.time.history = cfg.time.history[:1]
        cfg.time.history[0].dt = 21600.0
        if short_pwf is not None:
            cfg.time.history[0].p_wf = short_pwf
    return cfg


def run(cfg, theta):
    sim, init = SimulatorFactory.from_config(cfg)
    if theta:
        en = sim._energy
        held = {}
        asm0, solve0 = en.assemble_tridiag, en.solve_banded_system

        def asm(N, dt, T_old, T_ext, *rest):
            held["T_ref"] = T_ext
            return asm0(N, dt, T_old - T_ext, T_ext - T_ext, *rest)

        def solve(a, b, c, d, N):
            th = solve0(a, b, c, d, N)
            held["theta"] = th
            return th + held["T_ref"]

        def add_substep(self, *args, T_ext, **kw):
            _SUB0(self, *args, T_ext=T_ext - T_ext, **kw)
            self._probe_T_ref = T_ext

        def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
            _ACC0(self, held["theta"], T_prev - self._probe_T_ref, rho_cp_eff, dt)

        en.assemble_tridiag = asm
        en.solve_banded_system = solve
        EnergyBalanceAccumulator.add_substep = add_substep
        EnergyBalanceAccumulator.add_accumulation = add_accumulation
    try:
        h = sim.run(init)
    finally:
        EnergyBalanceAccumulator.add_substep = _SUB0
        EnergyBalanceAccumulator.add_accumulation = _ACC0
    bal = compute_balance(h, sim._grid, cfg)
    return h, bal


def main():
    names = sys.argv[1:] or ALL
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}; dt={os.environ.get('DEBT043_DT', 'конфиг')}; "
          f"short={bool(os.environ.get('DEBT043_SHORT'))}", flush=True)
    print(" пример                       | отн. сейчас | отн. в θ  | max по записям в θ | |невязка| в θ, Дж"
          " | max|ΔT|, К | max|Δp|, Па | max|ΔSg|")
    worst = 0.0
    cases = [(n, None) for n in names]
    if os.environ.get("DEBT043_SHORT"):
        cases = [("03_standing_corey", None), ("04_table_table", None), ("04_table_table", 16e6)]
    for name, pwf in cases:
        hT, bT = run(config(name, pwf), theta=False)
        hQ, bQ = run(config(name, pwf), theta=True)
        dT = max(float(np.max(np.abs(a.T - b.T))) for a, b in zip(hT.states, hQ.states))
        dp = max(float(np.max(np.abs(a.p - b.p))) for a, b in zip(hT.states, hQ.states))
        dS = max(float(np.max(np.abs(a.Sg - b.Sg))) for a, b in zip(hT.states, hQ.states))
        relQ = float(bQ["rel_residual"][-1])
        maxQ = float(np.max(bQ["rel_residual"][1:]))
        worst = max(worst, maxQ)
        tag = name if pwf is None else f"{name} p_wf={pwf:g}"
        print(f" {tag:28s} | {bT['rel_residual'][-1]:.2e}    | {relQ:.2e}  | {maxQ:.2e}           "
              f"| {abs(bQ['residual'][-1]):.2e}          | {dT:.1e}    | {dp:.1e}     | {dS:.1e}",
              flush=True)
    print(f"\nхудшая относительная невязка в θ (max по записям): {worst:.2e}")


if __name__ == "__main__":
    main()
