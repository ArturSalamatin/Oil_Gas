"""FEAT-025: числа плана и тестов для примеров 19–21 (конфиги — probes/final/<имя>).

Замеряется для каждого примера:
  - таблица по записям 0..30 сут: q_o, q_g, GOR, T(r_w), ΔT, S_g(r_w), R_s(r_w), p[0];
  - число принятых подшагов (дробление), время sim.run;
  - min_t (p_{N-1} - p_b), S_g и R_s контурной ячейки;
  - согласованность газа и давления (логика test_gas_active_cells_match_pressure
    примера 14): S_g > 0 <=> regime = 1; p < p_b => двухфазна; двухфазна при p >= p_b
    только с S_g > 1e-8;
  - профиль на 30 сут в выбранных точках;
  - баланс энергии;
  - сверка матрицы энергии с эталоном test_energy_matrix_examples (вызовы, max отн.).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\plan_numbers.py [имя ...]
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "tests", SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
import test_energy_matrix_examples as tm  # noqa: E402

DAY = 86400.0
NAMES = ["19_rs150_cooling", "20_rs500_cooling", "21_rs100_cooling"]
R_PROFILE = [0.11, 0.5, 1.0, 3.0, 10.0, 30.0, 60.0, 100.0, 130.0, 160.0, 190.0]


class Counting:
    """Обёртка EnergySolver.solve: длины принятых подшагов."""

    def __init__(self, inner):
        self._inner, self.dts = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        self.dts.append(dt)
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def numbers(name):
    cfg = load_config(HERE / "final" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    cnt = Counting(sim._energy)
    sim._energy = cnt
    t0 = time.perf_counter()
    h = sim.run(init)
    el = time.perf_counter() - t0
    grid, pvt = sim._grid, cnt._inner._pvt
    r = grid.r_centers
    T0, Rs0 = cfg.initial_conditions.T0, cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    print(f"\n{'═' * 70}\n{name}: p_b = {pb/1e6:.4f} МПа, p0 = {cfg.initial_conditions.p0/1e6} МПа, "
          f"N = {cfg.grid.N}; sim.run {el:.1f} с; подшагов {len(cnt.dts)} "
          f"(интервалов {len(cfg.time.history)}), min dt {min(cnt.dts):.0f} с")
    print(f"{'сут':>4} | {'q_o,1e-3':>9} {'q_g':>8} {'GOR':>7} | {'T_w':>8} {'ΔT':>7} | "
          f"{'Sg_w':>6} {'Rs_w':>7} {'p0,МПа':>7} | {'2ф':>3} {'дальн':>6} | {'pN-pb,кПа':>9}")
    margins = []
    for n, st in enumerate(h.states):
        w = h.well_data[n]
        g = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
        tp = np.flatnonzero(st.Sg > 0)
        far = r[tp[-1]] if tp.size else 0.0
        margins.append(st.p[-1] - pb)
        print(f"{h.times[n]/DAY:4.0f} | {w.q_o_std*1e3:9.4f} {w.q_g_std:8.5f} {g:7.2f} | "
              f"{st.T[0]:8.3f} {st.T[0]-T0:+7.3f} | {st.Sg[0]:6.4f} {st.Rs[0]:7.3f} "
              f"{st.p[0]/1e6:7.4f} | {tp.size:3d} {far:6.1f} | {(st.p[-1]-pb)/1e3:9.1f}")
    # Контур
    print(f"контур: min_t (p_N-1 - p_b) = {min(margins)/1e3:+.1f} кПа; "
          f"max S_g[N-1] = {max(st.Sg[-1] for st in h.states):.3e}; "
          f"max |R_s[N-1] - R_s0| = {max(abs(st.Rs[-1]-Rs0) for st in h.states):.3e}")
    # Монотонность по записям 1..30
    qo = np.array([w.q_o_std for w in h.well_data[1:]])
    qg = np.array([w.q_g_std for w in h.well_data[1:]])
    gor = qg / qo
    Tw = np.array([st.T[0] for st in h.states[1:]])
    print(f"GOR: {gor[0]:.2f} → {gor[-1]:.2f}, строго растёт: {bool(np.all(np.diff(gor) > 0))}, "
          f"min ΔGOR = {np.diff(gor).min():.4f}, все < R_s0: {bool(np.all(gor < Rs0))}")
    print(f"q_o строго убывает: {bool(np.all(np.diff(qo) < 0))}; "
          f"T_w строго убывает: {bool(np.all(np.diff(Tw) < 0))}; "
          f"q_g монотонен: {bool(np.all(np.diff(qg) > 0)) or bool(np.all(np.diff(qg) < 0))}")
    dT = Tw - T0
    print(f"ΔT(r_w) по записям 1..30: от {dT.max():+.3f} до {dT.min():+.3f} К; "
          f"T_well(30) = {Tw[-1]:.3f} К; S_g(r_w, 30) = {h.states[-1].Sg[0]:.4f}")
    # Газ и давление
    ok1 = ok2 = ok3 = True
    worst_above = np.inf
    for st in h.states:
        below = st.p < pb
        two = st.regime == 1
        ok1 &= bool(np.array_equal(st.Sg > 0.0, two))
        ok2 &= bool(np.all(two[below]))
        above = two & ~below
        if above.any():
            worst_above = min(worst_above, float(st.Sg[above].min()))
            ok3 &= bool(np.all(st.Sg[above] > 1e-8))
    print(f"газ/давление: S_g>0 <=> regime=1: {ok1}; p<p_b => 2ф: {ok2}; "
          f"2ф при p>=p_b только с S_g>1e-8: {ok3} (min S_g таких {worst_above:.3e})")
    # Профиль на 30 сут
    st = h.states[-1]
    print(f"профиль на {h.times[-1]/DAY:.0f} сут:")
    for rr in R_PROFILE:
        j = int(np.argmin(np.abs(r - rr)))
        print(f"   r = {r[j]:7.2f} м: p = {st.p[j]/1e6:7.3f} МПа, S_g = {st.Sg[j]:.4f}, "
              f"ΔT = {st.T[j]-T0:+.3f} К")
    bal = compute_balance(h, grid, cfg)
    print(f"баланс энергии: rel_residual = {bal['rel_residual'][-1]:.2e}")


def matrix(name):
    """Сверка матрицы энергии — логика test_matrix_matches_reference."""
    cfg = load_config(HERE / "final" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    n, worst = [0], [0.0]

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        ref = tm.build_reference(sim._grid, sim._pvt, cfg.rock, hydro_result, state_prev, dt, bc)
        for k, x, y in zip("abcd", (a, b, c, d), ref):
            # Вариант Б плана: у правой части d — atol = RTOL·max|d_ref|
            # (d проходит через ноль, поэлементный rtol там — шум сокращения)
            atol = tm.RTOL * float(np.max(np.abs(y))) if k == "d" else 0.0
            np.testing.assert_allclose(x, y, rtol=tm.RTOL, atol=atol)
            m = np.abs(y) > 0
            if m.any():
                worst[0] = max(worst[0], float(np.max(np.abs(x[m] - y[m]) / np.abs(y[m]))))
        assert a[0] == 0.0 and c[-1] == 0.0
        n[0] += 1

    sim._energy.matrix_probe = probe
    t0 = time.perf_counter()
    sim.run(init)
    print(f"сверка матрицы: вызовов {n[0]}, max отн. расхождение {worst[0]:.2e} "
          f"(порог {tm.RTOL:.0e}), {time.perf_counter() - t0:.1f} с")


if __name__ == "__main__":
    for nm in sys.argv[1:] or NAMES:
        numbers(nm)
        matrix(nm)
