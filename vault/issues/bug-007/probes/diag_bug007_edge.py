"""BUG-007, подводные камни фикса.

1. Противоток фаз: бывает ли Phi_o и Phi_g разных знаков на одной грани?
   Если да, шаблон Phi_plus/Phi_minus обязателен (телескопировать нельзя).
2. Забой: T_left[0] = T[0] — соответствует ли это b[0] в assemble_tridiag?
   В матрице: b[0] содержит (+Phi_plus[0] - Phi_minus[0]), то есть грань 0
   даёт вклад Phi_plus[0]*T[0] + Phi_minus[0]*T[0] — обе ветви на ячейку 0.
3. Прямая сверка потока грани 0 и N с коэффициентами матрицы на одном шаге.
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

EXAMPLE = sys.argv[1] if len(sys.argv) > 1 else "04a_high_gas_saturation"

stats = {"counter": 0, "total": 0, "sign0": set(), "signN": set()}
_orig = TridiagEnergySolver.compute_convective_coefficients


def patched(self, Q_o, Q_g, rho_o, rho_g, c_p_o, c_p_g, N):
    Phi_plus, Phi_minus, Phi_o, Phi_g = _orig(
        self, Q_o, Q_g, rho_o, rho_g, c_p_o, c_p_g, N)
    # противоток: знаки Phi_o и Phi_g различны и оба ненулевые
    opp = (Phi_o * Phi_g < 0)
    stats["counter"] += int(np.count_nonzero(opp))
    stats["total"] += Phi_o.size
    stats["sign0"].add(int(np.sign(Phi_o[0] + Phi_g[0])))
    stats["signN"].add(int(np.sign(Phi_o[N] + Phi_g[N])))
    return Phi_plus, Phi_minus, Phi_o, Phi_g


TridiagEnergySolver.compute_convective_coefficients = patched
try:
    cfg = load_config(ROOT / "examples" / EXAMPLE / "config.json")
    cfg.output.log_level = "WARNING"
    sim, init = SimulatorFactory.from_config(cfg)
    sim.run(init)
finally:
    TridiagEnergySolver.compute_convective_coefficients = _orig

print(f"=== {EXAMPLE} ===")
print(f"граней с противотоком фаз: {stats['counter']} из {stats['total']}")
print(f"знак суммарного Phi на забое (грань 0): {sorted(stats['sign0'])}")
print(f"знак суммарного Phi на контуре (грань N): {sorted(stats['signN'])}")
print()
print("Трактовка:")
print(" противоток > 0  => шаблон Phi_plus/Phi_minus обязателен")
print(" знак на забое -1 => Phi_minus[0] активна, Phi_plus[0] = 0")
