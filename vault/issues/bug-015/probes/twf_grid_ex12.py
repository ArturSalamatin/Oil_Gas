"""BUG-015, замер при планировании: погрешность T_wf = T[0] на примере 12.

Пример 12 (двухфазная зона у забоя, μ_JT,o = −4e-7, μ_JT,g = 4e-6 К/Па)
считается на сетках N = 50, 100, 200. Для суток 1, 5, 15 печатает:
  - T[0] на каждой сетке и предел T(r_w) по Ричардсону первого порядка
    (T∞ ≈ 2·T_200 − T_100: при N → ∞ центр r_0 → r_w);
  - оценку поправки полуячейки по JT
    ΔT_½ = Σ_α μ_α·Φ_α,½ / Σ_α Φ_α,½ · (p_wf − p[0])
    (стационарный баланс полуячейки [r_w, r_0] без накопления,
    теплопроводности и дегазации — вариант 2 issue #115).
Вопрос: какую часть ошибки T[0] − T(r_w) на штатной сетке даёт JT
полуячейки и какую — остальное (дегазация, нестационарность).

Запуск из numerical_solver/ (~3–5 мин):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-015\\probes\\twf_grid_ex12.py
"""

import sys
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
print(f"Код: {SOLVER}")
sys.path.insert(0, str(SOLVER))

from gpn_multiphase_solver.cli import configure_batch_run  # noqa: E402
configure_batch_run()

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CONFIG = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"
GRIDS = (50, 100, 200)
DAYS = (1, 5, 15)


def half_cell(sim, state, hydro):
    """ΔT_½ — JT на полуячейке [r_w, r_0] по свойствам ячейки 0, К."""
    pvt = sim.pvt
    p = state.p[:1]
    T = state.T[:1]
    Rs = state.Rs[:1]
    # Φ_α = ρ_α·c_p,α·Q_α на забойной грани (ячейка 0 выше по потоку)
    Phi_o = (pvt.rho_o(p, Rs) * pvt.c_p_oil(p, T))[0] * hydro.Q_o[0]
    Phi_g = (pvt.rho_g(p) * pvt.c_p_gas(p, T))[0] * hydro.Q_g[0]
    mu_o = pvt.mu_JT_oil(p, T)[0]
    mu_g = pvt.mu_JT_gas(p, T)[0]
    Phi = Phi_o + Phi_g
    if Phi == 0.0:
        return 0.0, 0.0, 0.0
    mu_eff = (mu_o * Phi_o + mu_g * Phi_g) / Phi
    # Дегазация на той же полуячейке: нефть выше по потоку — ячейка 0
    # (R_s[0]), на забое — равновесный R_s(p_wf). Мощность по образцу правой
    # грани eq:mdot_disc: V·Q_deg = L·ρ_g,ст·G^o·(R_s,выше − R_s,ниже) < 0 —
    # охлаждение; делится на |ΣΦ|, как JT-поправка.
    Rs_w = min(pvt.Rs_eq(np.array([hydro.p_wf]))[0], Rs[0])
    L = pvt.L_degas(p, T)[0]
    P_deg = L * pvt.rho_g_std * hydro.G_o[0] * (Rs[0] - Rs_w)
    dT_deg = P_deg / abs(Phi)
    return mu_eff * (hydro.p_wf - state.p[0]), mu_eff, dT_deg


def run(N):
    config = load_config(CONFIG)
    config.grid.N = N
    sim, init = SimulatorFactory.from_config(config)
    t0 = time.time()
    hist = sim.run(init)
    out = {}
    for d in DAYS:
        k = int(np.argmin(np.abs(np.array(hist.times) - d * 86400.0)))
        st, hy = hist.states[k], hist.hydro_results[k]
        dT, mu_eff, dT_deg = half_cell(sim, st, hy)
        out[d] = dict(T0=st.T[0], p0=st.p[0], pwf=hy.p_wf, Sg0=st.Sg[0],
                      dT=dT, mu_eff=mu_eff, dT_deg=dT_deg,
                      r0=sim.grid.r_centers[0])
    print(f"N = {N}: {time.time() - t0:.0f} с")
    return out


def main():
    res = {N: run(N) for N in GRIDS}
    for d in DAYS:
        print(f"\n── сутки {d} ──")
        print("   N    r_0, м    Sg[0]    p[0]−p_wf, кПа   μ_eff, К/МПа"
              "   T[0], К      ΔT_½, К")
        for N in GRIDS:
            r = res[N][d]
            print(f" {N:4d}   {r['r0']:.4f}   {r['Sg0']:.4f}   "
                  f"{(r['p0'] - r['pwf']) / 1e3:10.2f}      "
                  f"{r['mu_eff'] * 1e6:8.3f}    {r['T0']:.5f}   {r['dT']:+.5f}")
        T50, T100, T200 = (res[N][d]["T0"] for N in GRIDS)
        T_inf = 2 * T200 - T100
        print(f"  приращения T[0]: 50→100 {T100 - T50:+.5f}, "
              f"100→200 {T200 - T100:+.5f} К; отношение "
              f"{(T100 - T50) / (T200 - T100):.2f}")
        print(f"  T∞ (Ричардсон 1-го порядка) = {T_inf:.5f} К")
        for N in GRIDS:
            r = res[N][d]
            both = r['dT'] + r['dT_deg']
            print(f"  N = {N:3d}: T∞ − T[0] = {T_inf - r['T0']:+.5f} К,"
                  f" ΔT_½ = {r['dT']:+.5f}, ΔT_deg = {r['dT_deg']:+.5f},"
                  f" T∞ − (T[0] + ΔT_½) = {T_inf - r['T0'] - r['dT']:+.5f},"
                  f" T∞ − (T[0] + ΔT_½ + ΔT_deg) = {T_inf - r['T0'] - both:+.5f} К")


if __name__ == "__main__":
    main()
