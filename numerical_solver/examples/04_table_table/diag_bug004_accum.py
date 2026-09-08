"""BUG-004, шаг 2: подтвердить, что весь дефицит — в дискретизации накопления.

Установлено diag_bug004.py: невязка схемы ~1e-12, всё расхождение в члене
накопления. Здесь проверяем конкретную формулу.

Решатель:  E_acc = Σ_n Σ_j V_j (ρcp)^{n+1}_j (T^{n+1}_j - T^n_j)
Скрипт:    ΔE    = Σ_j V_j [(ρcp)^K_j T^K_j - (ρcp)^0_j T^0_j]

Разность тождественно равна  Σ_n Σ_j V_j T^n_j [(ρcp)^{n+1}_j - (ρcp)^n_j].
Считаем этот член напрямую и сверяем с наблюдаемой невязкой.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\diag_bug004_accum.py
"""

import sys
from pathlib import Path
import numpy as np

_HERE = Path(__file__).resolve().parent
_EXAMPLES = _HERE.parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES), str(_EXAMPLES / "03_standing_corey")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
if _PROTO.exists() and str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
import energy_balance as eb


def check(config_path, label):
    cfg = load_config(Path(config_path))
    sim, init = SimulatorFactory.from_config(cfg)
    history = sim.run(init)

    grid = sim._grid
    V = grid.volumes
    pvt = sim._energy._pvt
    rock = sim._energy._rock

    n_steps = len(history.times)

    # (ρcp)_eff на каждом сохранённом шаге — той же функцией, что и в скрипте.
    rho_cp = []
    for n in range(n_steps):
        st = history.states[n]
        *_, rc = eb._cell_properties(pvt, rock, st.p, st.Sg, st.Rs, st.T)
        rho_cp.append(rc)

    # Член-виновник: Σ_n Σ_j V T^n [(ρcp)^{n+1} - (ρcp)^n]
    drift = 0.0
    for n in range(n_steps - 1):
        T_n = history.states[n].T
        drift += float(np.sum(V * T_n * (rho_cp[n + 1] - rho_cp[n])))

    # Накопление «как в схеме»: Σ V (ρcp)^{n+1} (T^{n+1} - T^n)
    acc_scheme = 0.0
    for n in range(n_steps - 1):
        T_n = history.states[n].T
        T_np1 = history.states[n + 1].T
        acc_scheme += float(np.sum(V * rho_cp[n + 1] * (T_np1 - T_n)))

    bal = eb.compute_balance(history, grid, cfg)
    dE_script = float(bal['delta_E'][-1])
    resid_script = float(bal['residual'][-1])

    # Относительное изменение (ρcp)_eff: средн. по области и макс. поячеечно
    rc0, rcK = rho_cp[0], rho_cp[-1]
    rel_mean = abs(np.sum(V * rcK) - np.sum(V * rc0)) / np.sum(V * rc0)
    rel_max = float(np.max(np.abs(rcK - rc0) / rc0))

    print(f"\n=== {label} ===")
    print(f"  ΔE скрипта              = {dE_script:+.4e} Дж")
    print(f"  накопление как в схеме  = {acc_scheme:+.4e} Дж")
    print(f"  член-дрейф Σ V T Δ(ρcp) = {drift:+.4e} Дж")
    print(f"  тождество: ΔE - acc     = {dE_script - acc_scheme:+.4e}")
    print(f"             drift        = {drift:+.4e}")
    print(f"    сходится: {abs((dE_script - acc_scheme) - drift) / max(abs(drift), 1e-30):.3e}")
    print(f"  невязка скрипта         = {resid_script:+.4e} Дж")
    print(f"  доля дрейфа в невязке   = {drift / resid_script if resid_script else float('nan'):.4f}")
    print(f"  изм. (ρcp)_eff: средн. {rel_mean:.4%}, макс. по ячейкам {rel_max:.4%}")


if __name__ == "__main__":
    check(_HERE / "config.json", "Пример 04 (табличный PVT)")
    check(_EXAMPLES / "03_standing_corey" / "config.json", "Пример 03 (Standing)")
