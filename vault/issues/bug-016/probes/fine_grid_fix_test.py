"""FEAT-024: проверка причин отказа первого шага примера 14 на мелкой сетке.

Две правки прототипа — только в этой пробе, через подмену методов модели:
  cap  — начальное S_g ячейки, активированной в цикле по набору фаз,
         ограничено сверху (у прототипа: выделение «в закрытом сосуде»,
         0.55-0.71 при R_s0 = 150 против ~0.22 в решении);
  l2   — линейный поиск принимает шаг по уменьшению ||F||_2, а не ||F||_inf.
Режим none — исходный алгоритм (контроль).

Запуск (из numerical_solver рабочего дерева .worktrees/feat-024):
    python <этот файл> N dt_s mode[,mode] [full]
    full — после первого шага полный расчёт 360 сут, печать S_g(r) и итогов.
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("HydroSolverPrototype/Prototype_1.0.3").resolve()))
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport, BlackOilState  # noqa: E402

BAR = 1e5
N, dt = int(sys.argv[1]), float(sys.argv[2])
modes = set(sys.argv[3].split(","))
full = len(sys.argv) > 4 and sys.argv[4] == "full"
SG_CAP = 0.3

cfg = load_config(Path("examples/14_high_gor_cooling/config.json"))
cfg.grid.N = N
sim, init = SimulatorFactory.from_config(cfg)
m = sim._hydro._model


def newton(z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
    """Копия _newton_fixed_active_set; в режиме l2 — другая норма линейного поиска."""
    merit = (lambda f: np.linalg.norm(f)) if "l2" in modes else (lambda f: np.linalg.norm(f, np.inf))
    z = np.asarray(z0, float).copy()
    scale = max(np.linalg.norm(m.residual(z, state_old, dt_s, gas_active), np.inf), 1e-9)
    for it in range(1, max_iter + 1):
        J, f = m.finite_difference_jacobian(z, state_old, dt_s, gas_active)
        nrm = np.linalg.norm(f, np.inf)
        # Критерий сходимости — прежний (норма inf), меняется только линейный поиск
        if nrm <= atol_sm3s + rtol * scale:
            return z, BlackOilNewtonReport(True, it - 1, float(nrm))
        dz = m._linear_solve(J, -f)
        mf = merit(f)
        alpha, accepted = 1.0, False
        for _ in range(12):
            trial = z + alpha * dz
            if m._trial_is_reasonable(trial, gas_active):
                if merit(m.residual(trial, state_old, dt_s, gas_active)) < mf:
                    z, accepted = trial, True
                    break
            alpha *= 0.5
        if not accepted:
            return z, BlackOilNewtonReport(False, it, float(nrm))
    f = m.residual(z, state_old, dt_s, gas_active)
    return z, BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)))


def advance_phases(state_old, dt_s, max_active_iter=12, max_newton=15):
    """Копия _advance_phases; в режиме cap начальное S_g активации <= SG_CAP."""
    state_old = state_old.copy()
    mask = state_old.gas_active.copy()
    guess = state_old.copy()
    total_switches = total_newton = 0
    for aset in range(1, max_active_iter + 1):
        z, report = m._newton_fixed_active_set(m.pack(guess, mask), state_old, dt_s, mask,
                                               max_iter=max_newton)
        total_newton += report.iterations
        if not report.converged:
            report.active_set_iterations = aset
            report.phase_switches = total_switches
            return guess, report
        trial = m.unpack(z, mask)
        rs_sat = m.pvt.rs_sat(trial.pressure_bar)
        activate = (~mask) & (trial.rs_sm3_sm3 > rs_sat + m.rs_switch_tol)
        deactivate = mask & (trial.sg < -m.sg_switch_tol)
        ns = int(np.count_nonzero(activate) + np.count_nonzero(deactivate))
        total_switches += ns
        if ns == 0:
            tiny = mask & (trial.sg < 0) & (trial.sg >= -m.sg_switch_tol)
            trial.sg[tiny] = 0.0
            trial.gas_active = mask.copy()
            report.iterations = total_newton
            report.active_set_iterations = aset
            report.phase_switches = total_switches
            return trial, report
        newmask = mask.copy()
        newmask[activate] = True
        newmask[deactivate] = False
        guess = trial.copy()
        guess.gas_active = newmask.copy()
        if np.any(activate):
            pa = guess.pressure_bar[activate]
            rtot = guess.rs_sm3_sm3[activate].copy()
            rsat = m.pvt.rs_sat(pa)
            bo, bg = m.pvt.bo(pa, rsat), m.pvt.bg(pa)
            d = np.maximum(rtot - rsat, 0.0)
            sg0 = np.maximum(d * bg / (bo + d * bg), 1e-8)
            guess.sg[activate] = np.minimum(sg0, SG_CAP) if "cap" in modes else sg0
            guess.rs_sm3_sm3[activate] = rsat
        if np.any(deactivate):
            guess.sg[deactivate] = 0.0
            guess.rs_sm3_sm3[deactivate] = m.pvt.rs_sat(guess.pressure_bar[deactivate])
        mask = newmask
    r = m.residual(m.pack(guess, mask), state_old, dt_s, mask)
    return guess, BlackOilNewtonReport(False, total_newton, float(np.linalg.norm(r, np.inf)),
                                       max_active_iter, total_switches)


m._newton_fixed_active_set = newton
m._advance_phases = advance_phases

m.set_bhp_control(6.0e6 / BAR)
s0 = BlackOilState(pressure_bar=init.p / BAR, rs_sm3_sm3=init.Rs.copy(),
                   sg=init.Sg.copy(), gas_active=(init.regime == 1))
new, rep = m.advance(s0, dt)
print(f"N = {N}, dt = {dt:g} с, режим {sorted(modes)}: сошёлся = {rep.converged}, "
      f"fallback = {getattr(rep, 'fallback', False)}, итераций Ньютона {rep.iterations}"
      + (f", S_g[0] = {new.sg[0]:.4f}" if rep.converged else ""))

if full and rep.converged:
    t0 = time.perf_counter()
    h = sim.run(init)
    st, wd = h.states[-1], h.well_data[-1]
    r = sim._grid.r_centers
    print(f"полный расчёт: {time.perf_counter() - t0:.1f} с; T(r_w) = {st.T[0]:.3f} К, "
          f"S_g(r_w) = {st.Sg[0]:.4f}, q_o = {wd.q_o_std:.4e}, GOR = {wd.q_g_std / wd.q_o_std:.2f}")
    np.savetxt(Path(__file__).resolve().parent / f"sgdiag/profile_N{N}_{'_'.join(sorted(modes))}.csv",
               np.column_stack([r, st.p, st.Sg, st.T]), delimiter=",",
               header="r_m,p_Pa,Sg,T_K", comments="")
    for rr in (0.11, 0.5, 1.0, 2.0, 10.0, 30.0, 40.0, 50.0, 64.0, 80.0, 100.0, 115.0):
        print(f"  r = {rr:6.2f} м: S_g = {np.interp(rr, r, st.Sg):.4f}")
