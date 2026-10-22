"""FEAT-020, аудит плана (раунд 1): проверка сценариев тестов до реализации.

P1. Сценарии TestAdapterWellPressure / TestAdapterRateControl — на прототипе
    напрямую, с параметрами фикстур tests/test_prototype_adapter.py
    (p0 = 200 бар, N = 20, R = 50 м): сходимость и значения q, p_bhp.
P2. Код stationary_pwf из плана (§8, шаг 8) — на конфиге примера 12 с
    историей из одного интервала управления по дебиту.
P3. Тест притока через забой (TestWellPressureSource): HydroResult
    собирается из производственного подменой потока на забойной грани
    (compute_fluxes после DEBT-019 приток запретит); зависимость T[0]
    от p_wf. Энергия сейчас берёт p_wf из bc.well — зависимость та же.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-020\\probes\\audit_checks.py
"""

import copy
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from radial_blackoil.grid import RadialGrid  # noqa: E402
from radial_blackoil.rock import CompressibleRock  # noqa: E402
from radial_blackoil.pvt import BlackOilPVT  # noqa: E402
from radial_blackoil.relperm import TabulatedRelPerm  # noqa: E402
from radial_blackoil.blackoil import RadialBlackOilModel  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypePVTAdapter  # noqa: E402
from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions  # noqa: E402
from gpn_multiphase_solver.bc import PressureControl  # noqa: E402
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter  # noqa: E402
from gpn_multiphase_solver.fluxes import compute_fluxes  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
from gpn_multiphase_solver.io.config import load_config, HistoryInterval, RockConfig  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA, M2_TO_MD  # noqa: E402
from closed_form import Closure, solve_closed  # noqa: E402

DAY = 86400.0


def part_p1():
    print("═" * 70 + "\nP1. Сценарии тестов адаптера (фикстуры test_prototype_adapter)\n" + "═" * 70)
    N, P0, PWF = 20, 200e5, 150e5
    oil = [(0.0, 50.0, 1.05, 3.0), (0.0, 300.0, 1.04, 3.2),
           (30.0, 150.0, 1.20, 1.5), (30.0, 300.0, 1.18, 1.6)]
    gas = [(50.0, 0.020, 0.012), (150.0, 0.008, 0.014), (300.0, 0.004, 0.018)]
    rp = TabulatedRelPerm([0.0, 0.1, 0.2, 0.4, 0.6, 0.8], [1.0, 0.8, 0.6, 0.3, 0.1, 0.0],
                          [0.0, 0.01, 0.05, 0.2, 0.5, 0.8])

    def fresh():
        pvt = BlackOilPVT(oil, gas)
        m = RadialBlackOilModel(grid=RadialGrid(0.1, 50.0, 10.0, N, 1e-13 * M2_TO_MD),
                                rock=CompressibleRock(phi_ref=0.2, p_ref_bar=P0 / BAR_TO_PA, cr_per_bar=0.0),
                                pvt=pvt, relperm=rp, p_bhp_bar=PWF / BAR_TO_PA,
                                p_outer_bar=P0 / BAR_TO_PA, outer_rs_sm3_sm3=30.0, skin=0.0)
        ad = PrototypeHydroAdapter(m, LogRadialGrid(r_well=0.1, R_ext=50.0, h=10.0, N=N, k=1e-13),
                                   PrototypePVTAdapter(pvt, rho_o_std=850.0, rho_g_std=0.85))
        return m, ad

    init = SimulationState(p=np.full(N, P0), Sg=np.zeros(N), Rs=np.full(N, 30.0),
                           T=np.full(N, 350.0), regime=np.full(N, 2, dtype=int), t=0.0)
    s0 = BlackOilState(np.full(N, P0 / BAR_TO_PA), np.full(N, 30.0), np.zeros(N), np.zeros(N, bool))

    # BHP, закрытие: уставка 250 бар при p0 = 200 бар
    m, ad = fresh()
    bc = BoundaryConditions(well=PressureControl(250e5), p_ext=P0, T_ext=350.0, Rs_ext=30.0)
    r = ad.solve(init, 3600.0, bc)
    bhp = m.well_rates(BlackOilState(r.state.p / BAR_TO_PA, r.state.Rs, r.state.Sg, r.state.regime == 1))['bhp_bar']
    print(f"  BHP 250 бар (закрыта): n_sub={r.n_substeps}, G_o[0]={r.G_o[0]!r}, "
          f"p[0]={r.state.p[0]:.6e}, bhp·1e5={bhp * BAR_TO_PA:.6e}, "
          f"равны: {bhp * BAR_TO_PA == r.state.p[0]}")

    # BHP, добыча: уставка 150 бар
    m, ad = fresh()
    bc = BoundaryConditions(well=PressureControl(PWF), p_ext=P0, T_ext=350.0, Rs_ext=30.0)
    r = ad.solve(init, 3600.0, bc)
    bhp = m.well_rates(BlackOilState(r.state.p / BAR_TO_PA, r.state.Rs, r.state.Sg, r.state.regime == 1))['bhp_bar']
    print(f"  BHP 150 бар (добыча): G_o[0]={r.G_o[0]:.4e}, bhp·1e5 == 15e6: {bhp * BAR_TO_PA == PWF}")

    # Управление по дебиту: прототип напрямую (адаптер — после реализации)
    cases = [("q=2, min=100", 2.0, 100.0), ("q=1000, min=100", 1000.0, 100.0),
             ("q=2, min=250 (закрыта)", 2.0, 250.0), ("q=0, min=100", 0.0, 100.0)]
    for name, q, pmin in cases:
        m, _ = fresh()
        m.set_oil_rate_control(q, pmin)
        s1, rep = m.advance(s0, 3600.0)
        w = m.well_rates(s1)
        print(f"  {name}: converged={rep.converged}, q={w['oil_sm3_s'] * DAY:.10g} м³/сут, "
              f"bhp={w['bhp_bar']:.6f} бар, p0={s1.pressure_bar[0]:.6f}, "
              f"constraint={w['constraint_active']}")
    # Смена режима: дебит -> давление
    m, _ = fresh()
    m.set_oil_rate_control(2.0, 100.0)
    s1, _ = m.advance(s0, 3600.0)
    m.set_bhp_control(PWF / BAR_TO_PA)
    s2, rep = m.advance(s1, 3600.0)
    w = m.well_rates(s2)
    print(f"  дебит -> давление: converged={rep.converged}, bhp={w['bhp_bar']!r}, "
          f"mode={w['control_mode']}, min_bhp_bar={m.min_bhp_bar}")


def stationary_pwf(config, pvt, relperm) -> float:
    """Копия кода из плана (§8, шаг 8)."""
    last = config.time.history[-1]
    if last.control == "pressure":
        return float(last.p_wf)
    Rs0 = config.initial_conditions.Rs0
    p_e = config.initial_conditions.p0
    q_last = float(last.q_oil)
    if q_last == 0.0:
        return float(p_e)
    clo = Closure(pvt, relperm, Rs0)
    pb = float(pvt.pb(np.array([Rs0]))[0])
    k, h = config.rock.permeability, config.geometry.h
    r_w, R_e = config.geometry.r_well, config.geometry.R_ext
    coef = 2.0 * np.pi * k * h / np.log(R_e / r_w)

    def q_of(p_wf):
        pts = [pb] if p_wf < pb < p_e else None
        val, _err = quad(clo.mob_o, p_wf, p_e, points=pts, limit=200, epsabs=1e-13, epsrel=1e-13)
        return coef * val

    p_min = float(last.min_bhp)
    if q_of(p_min) <= q_last:
        return p_min
    return float(brentq(lambda x: q_of(x) - q_last, p_min, p_e, xtol=1.0, rtol=1e-12))


def part_p2():
    print("\n" + "═" * 70 + "\nP2. stationary_pwf из плана\n" + "═" * 70)
    base = load_config(SOLVER / "examples" / "12_large_drainage_radius" / "config.json")
    base.output.log_level = "WARNING"
    sim, _ = SimulatorFactory.from_config(base)
    pvt, rp = sim._energy._pvt, _create_relperm(base)
    print(f"  давление (конфиг 12): {stationary_pwf(base, pvt, rp)!r}")
    for q_day in (270.0, 1000.0, 0.0):
        c = copy.deepcopy(base)
        c.time.history = [HistoryInterval(dt=DAY, control="rate", q_oil=q_day / DAY, min_bhp=101325.0)]
        t0 = time.perf_counter()
        pw = stationary_pwf(c, pvt, rp)
        el = time.perf_counter() - t0
        print(f"  q = {q_day:g} м³ст/сут: p_wf* = {pw:.6f} Па ({pw / 1e6:.5f} МПа), {el * 1e3:.0f} мс")
        if q_day == 270.0:
            # Сверка с solve_closed при найденном p_wf* (текущий код берёт p_wf из конфига)
            c2 = copy.deepcopy(base)
            c2.time.history[-1].p_wf = pw
            cl = solve_closed(c2, pvt, rp, sim._grid.r_centers)
            print(f"    solve_closed(p_wf*): q_o = {cl['q_o'] * DAY:.9f} м³ст/сут, "
                  f"отн. откл. {abs(cl['q_o'] - q_day / DAY) / (q_day / DAY):.2e}")


def part_p3():
    print("\n" + "═" * 70 + "\nP3. Приток через забой: T[0] от p_wf\n" + "═" * 70)
    N, P0, PWF, RS0 = 20, 20e6, 10e6, 50.0
    grid = LogRadialGrid(0.1, 50.0, 10.0, N, 1e-13)
    pvt = StandingFullPVT(rho_o_std=850.0, rho_g_std=0.85, T0=350.0, Rs0=RS0,
                          co_undersaturated=0.0, c_p_oil=2000.0, c_p_gas=1000.0,
                          mu_JT_oil_val=4e-7, mu_JT_gas_val=0.0, L_degas_val=0.0)
    rock = RockConfig(porosity=0.2, permeability=1e-13, rho_cp_solid=1.25e6,
                      lambda_solid=1.5, lambda_oil=0.14, lambda_gas=0.04)
    solver = TridiagEnergySolver(grid, pvt, rock)
    r = grid.r_centers
    p = PWF + (P0 - PWF) * np.log(r / grid.r_well) / np.log(grid.R_ext / grid.r_well)
    st = SimulationState(p=p, Sg=np.zeros(N), Rs=np.full(N, RS0), T=np.full(N, 350.0),
                         regime=np.full(N, 2, dtype=int), t=0.0)
    bc = lambda pw: BoundaryConditions(well=PressureControl(pw), p_ext=P0, T_ext=350.0, Rs_ext=RS0)  # noqa: E731
    hr = compute_fluxes(st, grid, pvt, CoreyRP(0.2, 0.05, 2.0, 2.0), bc(PWF))
    print(f"  добыча: Q_o[0] = {hr.Q_o[0]:.4e}, S_g макс = {st.Sg.max()}")
    Ta = solver.solve(hr, st, 3600.0, bc(PWF))
    Tb = solver.solve(hr, st, 3600.0, bc(1e5))
    print(f"  добыча, p_wf 10 МПа против 0.1 МПа: T побитово равна: {np.array_equal(Ta, Tb)}")
    # Приток: подмена потока на забойной грани (DEBT-019 запретит compute_fluxes с p_wf > p0)
    Q_o = hr.Q_o.copy()
    Q_o[0] = abs(Q_o[0])
    hin = replace(hr, Q_o=Q_o)
    Tc = solver.solve(hin, st, 3600.0, bc(PWF))
    Td = solver.solve(hin, st, 3600.0, bc(PWF - 1e6))
    print(f"  приток (Q_o[0] = +{Q_o[0]:.4e}): T[0] = {Tc[0]:.6f} / {Td[0]:.6f} К, "
          f"|ΔT[0]| = {abs(Tc[0] - Td[0]):.4e} К, конечна: {np.all(np.isfinite(Tc))}, "
          f"|ΔT[1:]| макс = {np.max(np.abs(Tc[1:] - Td[1:])):.3e} К")


def part_p4():
    """Смешанное расписание теста согласованности: 1-12 по дебиту, 13-24 по давлению."""
    print("\n" + "═" * 70 + "\nP4. Согласованность, смешанное расписание\n" + "═" * 70)
    sys.path.insert(0, str(HERE))
    import plan_numbers as pn
    p_steps = [14.4e6] * 12 + [13.8e6] * 12
    hist = [HistoryInterval(dt=3600.0, control="pressure", p_wf=pw) for pw in p_steps]
    _, sim_a, init = pn.build(hist)
    ha = sim_a.run(init)
    q_list = [w.q_o_std for w in ha.well_data[1:]]
    _, sim_b, init_b = pn.build(hist)
    pn.enable_rate(sim_b, q_list, 101325.0)
    # интервалы 13-24 возвращаются на управление по давлению
    for iv, pw in zip(sim_b._schedule.intervals[12:], p_steps[12:]):
        iv.bc.well = PressureControl(pw)
    hb = sim_b.run(init_b)
    mx = lambda f: max(float(np.max(np.abs(f(a) - f(b)))) for a, b in zip(ha.states, hb.states))  # noqa: E731
    dpwf = max(abs(a.p_wf - b.p_wf) for a, b in zip(ha.well_data[1:], hb.well_data[1:]))
    print(f"  max|Δp| = {mx(lambda s: s.p):.3e} Па, |ΔSg| = {mx(lambda s: s.Sg):.3e}, "
          f"|ΔRs| = {mx(lambda s: s.Rs):.3e}, |ΔT| = {mx(lambda s: s.T):.3e} К, |Δp_wf| = {dpwf:.3e} Па")


if __name__ == "__main__":
    part_p1()
    part_p2()
    part_p3()
    part_p4()
