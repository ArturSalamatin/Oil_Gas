"""BUG-004, шаг 3 диагностики: проверить ПРЕДЛАГАЕМЫЙ фикс до реализации.

Считает баланс по формулам, которые план предписывает внести в
compute_balance (накопление по приращениям + конвекция по всем граням),
не меняя сам energy_balance.py. Если невязка падает — фикс верен, и план
можно реализовывать без риска.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04_table_table\\diag_bug004_proposed.py
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


def balance_proposed(history, grid, config):
    """Баланс по формулам предлагаемого фикса (план BUG-004, шаг 2)."""
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt
    rock = sim._energy._rock

    N = grid.N
    V = grid.volumes
    phi = rock.porosity
    T_ext = config.initial_conditions.T0
    rho_g_std = pvt.rho_g_std

    n_steps = len(history.times)
    t_arr = np.array(history.times)

    delta_E = np.zeros(n_steps)
    cum_conv = np.zeros(n_steps)
    cum_adiab = np.zeros(n_steps)
    cum_jt = np.zeros(n_steps)
    cum_deg = np.zeros(n_steps)

    for n in range(n_steps):
        st = history.states[n]
        _, _, _, _, rho_cp_n = eb._cell_properties(
            pvt, rock, st.p, st.Sg, st.Rs, st.T)

        if n == 0:
            continue

        st_prev = history.states[n - 1]

        # ── НАКОПЛЕНИЕ: приращение с текущими свойствами (как в схеме) ──
        delta_E[n] = delta_E[n - 1] + np.sum(
            rho_cp_n * V * (st.T - st_prev.T))

        dt_step = t_arr[n] - t_arr[n - 1]
        hydro = history.hydro_results[n]

        p, Sg, Rs, T_prev = st.p, st.Sg, st.Rs, st_prev.T
        So = 1.0 - Sg
        Q_o, Q_g, G_o = hydro.Q_o, hydro.Q_g, hydro.G_o

        rho_o, rho_g, cp_o, cp_g, _ = eb._cell_properties(
            pvt, rock, p, Sg, Rs, T_prev)
        mu_JT_o = pvt.mu_JT_oil(p, T_prev)
        mu_JT_g = pvt.mu_JT_gas(p, T_prev)
        L = pvt.L_degas(p, T_prev)

        # ── КОНВЕКЦИЯ: Φ на всех гранях, upstream раздельно по фазам ──
        Phi_o = np.zeros(N + 1)
        Phi_g = np.zeros(N + 1)
        for f in range(1, N):
            up_o = f - 1 if Q_o[f] >= 0 else f
            Phi_o[f] = rho_o[up_o] * cp_o[up_o] * Q_o[f]
            up_g = f - 1 if Q_g[f] >= 0 else f
            Phi_g[f] = rho_g[up_g] * cp_g[up_g] * Q_g[f]
        Phi_o[0] = rho_o[0] * cp_o[0] * Q_o[0]
        Phi_g[0] = rho_g[0] * cp_g[0] * Q_g[0]
        Phi_o[N] = rho_o[-1] * cp_o[-1] * Q_o[N]
        Phi_g[N] = rho_g[-1] * cp_g[-1] * Q_g[N]

        Phi_plus = np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0)
        Phi_minus = np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0)

        T_left = np.concatenate(([T_prev[0]], T_prev))
        T_right = np.concatenate((T_prev, [T_ext]))
        flux = Phi_plus * T_left + Phi_minus * T_right
        net_conv = -(flux[N] - flux[0]) * dt_step

        # ── JT (без изменений: член уже совпадает с решателем) ──
        J_well = (mu_JT_o[0] * Phi_o[0] + mu_JT_g[0] * Phi_g[0]) * p[0]
        J_ext = (mu_JT_o[-1] * Phi_o[N] + mu_JT_g[-1] * Phi_g[N]) * p[-1]
        jt_step = (J_ext - J_well) * dt_step

        # ── Адиабатика (без изменений) ──
        dp = st.p - st_prev.p
        adiab_step = phi * np.sum(
            V * (So * (1.0 + rho_o * cp_o * mu_JT_o)
                 + Sg * (1.0 + rho_g * cp_g * mu_JT_g)) * dp)

        # ── Дегазация (без изменений) ──
        mdot_time = (-rho_g_std * phi * So / pvt.Bo(p, Rs)
                     * (Rs - st_prev.Rs) / dt_step)
        R_conv = np.zeros(N + 1)
        for f in range(1, N):
            Go_p, Go_m = max(G_o[f], 0.0), min(G_o[f], 0.0)
            R_conv[f] = Go_p * Rs[f - 1] + Go_m * Rs[f]
        R_conv[0] = G_o[0] * Rs[0]
        R_conv[N] = (G_o[N] * Rs[N - 1] if G_o[N] >= 0
                     else G_o[N] * st_prev.Rs[-1])
        mdot_conv = -rho_g_std * (R_conv[1:] - R_conv[:-1]) / V
        deg_step = np.sum(-L * (mdot_time + mdot_conv) * V) * dt_step

        cum_conv[n] = cum_conv[n - 1] + net_conv
        cum_adiab[n] = cum_adiab[n - 1] + adiab_step
        cum_jt[n] = cum_jt[n - 1] + jt_step
        cum_deg[n] = cum_deg[n - 1] + deg_step

    total = cum_conv + cum_adiab + cum_jt + cum_deg
    residual = delta_E - total
    scale = np.maximum(np.abs(delta_E), np.abs(total))
    scale = np.where(scale < 1e-10, 1.0, scale)

    return dict(t=t_arr, delta_E=delta_E, cum_adiab=cum_adiab,
                cum_conv=cum_conv, cum_jt=cum_jt, cum_deg=cum_deg,
                total=total, residual=residual,
                rel_residual=np.abs(residual) / scale)


def check(config_path, label):
    cfg = load_config(Path(config_path))
    cfg.output.log_level = "WARNING"
    sim, init = SimulatorFactory.from_config(cfg)
    history = sim.run(init)

    old = eb.compute_balance(history, sim._grid, cfg)
    new = balance_proposed(history, sim._grid, cfg)

    print(f"\n=== {label} ===")
    print(f"  невязка ТЕКУЩАЯ    = {old['rel_residual'][-1]:.4e}")
    print(f"  невязка ПРЕДЛАГАЕМАЯ = {new['rel_residual'][-1]:.4e}")
    r = old['rel_residual'][-1] / max(new['rel_residual'][-1], 1e-30)
    print(f"  улучшение          = {r:.1f}x")
    print(f"  cum_deg (новый)    = {new['cum_deg'][-1]:+.4e} Дж")
    return float(new['rel_residual'][-1])


if __name__ == "__main__":
    res = {}
    for name in ("03_standing_corey", "04_table_table", "05_standing_table_rp",
                 "06_table_corey_rp", "07_degassing_adiabatic_only",
                 "08_degassing_jt", "09_degassing_latent_heat",
                 "10_deep_degassing"):
        cfg_path = _EXAMPLES / name / "config.json"
        if not cfg_path.exists():
            print(f"\n[пропуск] {name}: нет config.json")
            continue
        try:
            res[name] = check(cfg_path, name)
        except Exception as e:
            print(f"\n[ОШИБКА] {name}: {type(e).__name__}: {e}")
            res[name] = float('nan')

    print("\n=== СВОДКА (невязка после предлагаемого фикса) ===")
    for k, v in res.items():
        flag = "OK" if v < 1e-2 else "ПРОВАЛ"
        print(f"  {k:32s} {v:.4e}  {flag}")
