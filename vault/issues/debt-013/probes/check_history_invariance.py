"""Аудит раунд 2: выдержит ли test_balance_independent_of_history_structure
сверку cum_conv с rel=1e-10 ПОСЛЕ фикса?

Тест сверяет накопленные члены при двух структурах истории (1 запись против 6).
Конвекция теперь считается по T^{n+1}, но T^{n+1} от структуры истории
не зависит — значит должно сойтись. Проверяем фактически.
"""
import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
SP = Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT / "examples"),
          str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import gpn_multiphase_solver  # noqa: F401
spec = importlib.util.spec_from_file_location(
    "gpn_multiphase_solver.energy.balance", SP / "balance_patched.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["gpn_multiphase_solver.energy.balance"] = mod
spec.loader.exec_module(mod)
import gpn_multiphase_solver.energy as energy_pkg
energy_pkg.balance = mod

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
import energy_balance as eb

_EXAMPLES = ROOT / "examples"


def run(example, n_intervals):
    """Точная копия функции run() из теста (строки 117-129)."""
    config = load_config(_EXAMPLES / example / "config.json")
    config.grid.N = 25
    iv = copy.deepcopy(config.time.history[0])
    config.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
    for h in config.time.history:
        h.dt = 21600.0 / n_intervals
    config.output.log_level = "WARNING"
    simulator, initial_state = SimulatorFactory.from_config(config)
    history = simulator.run(initial_state)
    assert history.n_saved == n_intervals + 1
    return eb.compute_balance(history, simulator._grid, config)


KEYS = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")

for example in ("03_standing_corey", "04_table_table"):
    sparse = run(example, 1)
    dense = run(example, 6)
    print(f"\n=== {example} ===")
    worst = 0.0
    for k in KEYS:
        a, b = float(sparse[k][-1]), float(dense[k][-1])
        rel = abs(a - b) / max(abs(a), abs(b), 1e-30)
        worst = max(worst, rel)
        flag = "  <<< ПРЕВЫШЕН 1e-10" if rel > 1e-10 else ""
        print(f"  {k:12s} {a:+14.6e} vs {b:+14.6e}  отн.разн={rel:.2e}{flag}")
    print(f"  худшее отклонение: {worst:.2e} (порог теста rel=1e-10)")
    for key, arr in (("sparse", sparse), ("dense", dense)):
        print(f"  {key} rel_residual = {abs(float(arr['rel_residual'][-1])):.4e}")
