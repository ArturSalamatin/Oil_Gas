"""FEAT-032 (планирование): откуда греется зона у забоя примера 17 — штатно и с нарастанием.

Перепроверка абзаца README 17 «Откуда тепло на останове» (замер FEAT-029,
vault/issues/feat-029/probes/local_budget.py): члены схемы энергии копятся по
ячейкам (перехват EnergyBalanceAccumulator.add_substep / add_accumulation), те
же выражения, что у local_budget.py:
  adiab_j = V_j Q_ad,j dt,  deg_j = V_j Q_deg,j dt,  jt_j = J_jt,j dt,
  conv_j  = -F_j dt (адвективная форма, eq:energy_conv_face),
  dE_j    = (ρc_p)_eff,j V_j (T^{n+1} - T^n),
  cond_j  = dE_j - (adiab + deg + jt + conv)_j — теплопроводность (остаток).
Конфиг — сам пример 17 (не перестроенный конфиг 20, как в FEAT-029);
нарастание — эмуляция варианта 2 (ramp_probe.patch), первый интервал сменой не считается.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P <h0, с | none>
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ramp_probe import SOLVER_ROOT, patch  # noqa: E402

from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator as Acc  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationHistory  # noqa: E402

KEYS = ("dE", "adiab", "deg", "jt", "conv")
E = 15


def main():
    h0 = None if sys.argv[1] == "none" else float(sys.argv[1])
    cfg = load_config(SOLVER_ROOT / "examples" / "17_shut_in_strong_cooling" / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    if h0 is not None:
        patch(sim, h0, include_first=False)
    grid = sim._grid
    V, N, r = grid.volumes, grid.N, grid.r_centers
    cum = {k: np.zeros(N) for k in KEYS}
    snaps, ctx = [], {}
    _add_sub, _add_acc, _append = Acc.add_substep, Acc.add_accumulation, SimulationHistory.append

    def add_substep(self, hydro_result, state_prev, dt, props, Phi_o, Phi_g,
                    Q_T_ext, J_jt, Q_ad, Q_deg, T_ext):
        cum["jt"] += J_jt * dt
        cum["adiab"] += V * Q_ad * dt
        cum["deg"] += V * Q_deg * dt
        ctx["Phi"] = (np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0),
                      np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0), dt, T_ext)
        return _add_sub(self, hydro_result, state_prev, dt, props, Phi_o, Phi_g,
                        Q_T_ext, J_jt, Q_ad, Q_deg, T_ext)

    def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
        Pp, Pm, dts, T_ext = ctx["Phi"]
        T_left = np.concatenate(([T_new[0]], T_new[:-1]))
        T_right = np.concatenate((T_new[1:], [T_ext]))
        F = Pp[0:N] * (T_new - T_left) + Pm[1:N + 1] * (T_right - T_new)
        cum["conv"] += -F * dts
        cum["dE"] += rho_cp_eff * V * (T_new - T_prev)
        return _add_acc(self, T_new, T_prev, rho_cp_eff, dt)

    def append(self, *a, **kw):
        snaps.append({k: v.copy() for k, v in cum.items()})
        return _append(self, *a, **kw)

    Acc.add_substep, Acc.add_accumulation, SimulationHistory.append = (
        add_substep, add_accumulation, append)
    h = sim.run(init)

    def seg(a, b):
        d = {k: snaps[b][k] - snaps[a][k] for k in KEYS}
        d["cond"] = d["dE"] - d["adiab"] - d["deg"] - d["jt"] - d["conv"]
        return d

    print(f"h0 = {h0}; T(r_w): конец добычи {h.states[E].T[0]:.4f}, +1 ч {h.states[E + 1].T[0]:.4f}")
    segs = [(E, E + 1, "1-й час"), (E + 1, E + 24, "2–24 ч"),
            (E + 24, len(snaps) - 1, "сутки 2–конец"), (E, len(snaps) - 1, "весь останов")]
    for rk in (1.0,):
        m = r < rk
        print(f"Зона r < {rk:g} м ({int(m.sum())} ячеек): доли ΔE, %  (ΔE, Дж)")
        for a, b, lab in segs:
            d = seg(a, b)
            dE = float(np.sum(d["dE"][m]))
            parts = " ".join(f"{k} {100 * float(np.sum(d[k][m])) / dE:+6.1f}"
                             for k in ("adiab", "deg", "conv", "jt", "cond"))
            print(f"  {lab:>14}: {parts}  (ΔE {dE:+.3e})")


if __name__ == "__main__":
    main()
