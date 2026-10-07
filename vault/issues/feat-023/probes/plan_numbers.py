"""FEAT-023: числа плана для примера 13б (замер до реализации, после BUG-014).

Конфиг — пример 12 (R_ext = 200 м, p0 = 15.5 МПа, p_b = 15 МПа, N = 50),
меняется только time.history: 60 интервалов по 43200 с, сутки 1..30,
нечётные 6 МПа, чётные 10.75 МПа. dt_integration = 3600 с, как в 12.

Что замеряется:
  - время sim.run, дробление шага (A-retry) по вызовам EnergySolver.solve;
  - закрытие скважины: принятые подшаги с G_o[0] = 0; закачка G_o[0] > 0;
  - отток на внутренних гранях (G > 0 на гранях 1..N-1) — Φ⁺ != 0;
  - переходы ячеек двухфазная -> однофазная и обратно;
  - таблица по записям: p_wf (фактическое, WellData), q_o, GOR, T(r_w),
    S_g(r_w), max S_g, двухфазные ячейки, недонасыщенная нефть;
  - проверка R_s = min(R_s^eq(p), R_s0) (report_rs) на конце 29 и 30 сут;
  - профили у забоя на концах 29 и 30 сут;
  - моменты профилей при n_profiles = 6 и 7;
  - баланс энергии;
  - длительность закрытия после первого и последнего скачка вверх (шаг 60 с);
  - при флаге --matrix: сверка матрицы энергии с эталоном
    tests/test_energy_matrix_examples.py (время и результат).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-023\\probes\\plan_numbers.py [--matrix]
"""

import copy
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
from rs_analytics import report_rs  # noqa: E402
from example_runner import _profile_times  # noqa: E402

BASE = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"
HALF_DAY = 43200.0
DAY = 86400.0


class Recording:
    """Обёртка EnergySolver.solve: пишет каждый ПРИНЯТЫЙ подшаг, физику не трогает."""

    def __init__(self, inner):
        self._inner, self.rows = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        st = hr.state
        N = len(st.p)
        self.rows.append(dict(
            t=st.t, dt=dt, G_o0=float(hr.G_o[0]), p0=float(st.p[0]),
            p_wf_set=float(bc.well.p_wf), p_wf_eff=float(hr.p_wf),
            # Отток от скважины на внутренних гранях: G > 0 (конвенция знаков)
            out_o=float(np.max(hr.G_o[1:N])), out_g=float(np.max(hr.G_free_gas[1:N])),
            Q_o0=float(hr.Q_o[0]), Q_g0=float(hr.Q_g[0]),
            n2=int(np.count_nonzero(st.regime == 1)),
            regime=st.regime.copy(), regime_prev=sp.regime.copy()))
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def schedule_13b():
    # Сутки 1..30: нечётные 6 МПа, чётные 10.75 МПа; по два интервала 0.5 сут
    return [(6.0e6 if d % 2 == 1 else 10.75e6) for d in range(1, 31) for _ in range(2)]


def make_cfg(pwfs, dt_hist=HALF_DAY, dt_int=3600.0):
    cfg = load_config(BASE)
    cfg.output.log_level = "ERROR"
    iv = cfg.time.history[0]
    hist = []
    for pw in pwfs:
        x = copy.deepcopy(iv)
        x.dt, x.p_wf = dt_hist, pw
        hist.append(x)
    cfg.time.history = hist
    cfg.time.dt_integration = dt_int
    return cfg


def run(cfg, state=None):
    sim, init = SimulatorFactory.from_config(cfg)
    rec = Recording(sim._energy)
    sim._energy = rec
    t0 = time.perf_counter()
    h = sim.run(init if state is None else state)
    return sim, rec, h, time.perf_counter() - t0


cfg = make_cfg(schedule_13b())
sim, rec, h, el = run(cfg)
grid, pvt = sim._grid, rec._inner._pvt
Rs0 = cfg.initial_conditions.Rs0
pb = float(pvt.pb(np.array([Rs0]))[0])
r = grid.r_centers

print(f"=== 13б: {len(cfg.time.history)} × {HALF_DAY:.0f} с, dt_integration = 3600 с ===")
print(f"sim.run {el:.1f} с; записей {len(h.states)}; принятых подшагов {len(rec.rows)}; "
      f"сумма dt {sum(x['dt'] for x in rec.rows):.0f} с")
dts = Counter(round(x["dt"], 3) for x in rec.rows)
print(f"dt: {dict(sorted(dts.items()))}")
sub = Counter()
for x in rec.rows:
    if x["dt"] < 3600.0 - 1e-9:
        sub[int((x["t"] - 1e-6) // DAY) + 1] += 1
print(f"сутки с дроблением (сутки: число мелких подшагов): {dict(sub)}")

shut = [x for x in rec.rows if x["G_o0"] == 0.0]
print(f"подшагов с закрытой скважиной (G_o[0] = 0): {len(shut)}")
for x in shut[:10]:
    print(f"   t = {x['t']/DAY:8.4f} сут, dt = {x['dt']:8.2f} с, p[0] = {x['p0']/1e6:.4f}, "
          f"p_wf зад./факт. = {x['p_wf_set']/1e6:.3f}/{x['p_wf_eff']/1e6:.4f} МПа")
print(f"подшагов с G_o[0] > 0 (закачка): {sum(1 for x in rec.rows if x['G_o0'] > 0.0)}; "
      f"max Q_o[0] = {max(x['Q_o0'] for x in rec.rows):.3e}, max Q_g[0] = "
      f"{max(x['Q_g0'] for x in rec.rows):.3e}")
print(f"отток на внутренних гранях: max G_o = {max(x['out_o'] for x in rec.rows):.3e}, "
      f"max G_free_gas = {max(x['out_g'] for x in rec.rows):.3e} м³ст/с; подшагов с G_o > 0: "
      f"{sum(1 for x in rec.rows if x['out_o'] > 0.0)}")

# Первый подшаг после каждого скачка вверх: t кратно 2 сут + 1 ч
print("первый подшаг каждых чётных суток (после скачка 6 -> 10.75):")
for d in range(2, 31, 2):
    t_first = (d - 1) * DAY
    xs = [x for x in rec.rows if t_first < x["t"] <= t_first + 3600.0 + 1e-6]
    if xs:
        x = xs[-1]
        print(f"   сутки {d:2d}: подшагов в 1-м часу {len(xs)}, G_o[0] = {x['G_o0']:+.3e}, "
              f"p[0] = {x['p0']/1e6:.4f}, p_wf факт. = {x['p_wf_eff']/1e6:.4f}")

up = [(x["t"], int(np.count_nonzero((x["regime_prev"] == 1) & (x["regime"] == 2))),
       int(np.count_nonzero((x["regime_prev"] == 2) & (x["regime"] == 1)))) for x in rec.rows]
print(f"переходов 2ф -> 1ф: {sum(a for _, a, _ in up)} (подшагов {sum(1 for _, a, _ in up if a)}); "
      f"1ф -> 2ф: {sum(b for _, _, b in up)} (подшагов {sum(1 for _, _, b in up if b)})")

print(f"\n{'сут':>5} | {'p_wf':>6} | {'q_o':>10} {'GOR':>7} | {'T_w':>8} {'S_g(r_w)':>8} "
      f"{'maxS_g':>7} {'r(max)':>7} | {'n_2ф':>4} {'r_2ф':>13} | {'p[0]':>7} | {'недонас':>7}")
for n, st in enumerate(h.states):
    w = h.well_data[n]
    tp = np.nonzero(st.Sg > 0)[0]
    g = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
    und = int(np.count_nonzero((st.regime == 2) & (st.p < pb)))
    jm = int(np.argmax(st.Sg))
    span = f"{r[tp[0]]:.2f}-{r[tp[-1]]:.1f}" if tp.size else "-"
    print(f"{h.times[n]/DAY:5.1f} | {w.p_wf/1e6:6.3f} | {w.q_o_std:10.4e} {g:7.2f} | "
          f"{st.T[0]:8.3f} {st.Sg[0]:8.4f} {st.Sg[jm]:7.4f} {r[jm]:7.2f} | "
          f"{tp.size:4d} {span:>13} | {st.p[0]/1e6:7.4f} | {und:7d}")

# p_wf записей против расписания
sched = schedule_13b()
dev = max(abs(h.well_data[n].p_wf - sched[n - 1]) for n in range(1, 61))
print(f"\nmax|p_wf записи - расписание| = {dev:.3e} Па; запись 0: p_wf = "
      f"{h.well_data[0].p_wf/1e6:.4f} МПа, p[0] = {h.states[0].p[0]/1e6:.4f}")

# Концы суток: 6 МПа (нечётные сутки, записи 2, 6, ...) против 10.75 (4, 8, ...)
q = np.array([w.q_o_std for w in h.well_data])
sgw = np.array([s.Sg[0] for s in h.states])
tw = np.array([s.T[0] for s in h.states])
lo_end = list(range(2, 61, 4))      # конец нечётных суток 1, 3, ..., 29 (6 МПа)
hi_end = list(range(4, 61, 4))      # конец чётных суток 2, 4, ..., 30 (10.75 МПа)
print(f"q_o концов 6 МПа:     {np.array2string(q[lo_end], precision=4)}")
print(f"q_o концов 10.75 МПа: {np.array2string(q[hi_end], precision=4)}")
print(f"S_g(r_w) концов 6:     {np.array2string(sgw[lo_end], precision=4)}")
print(f"S_g(r_w) концов 10.75: {np.array2string(sgw[hi_end], precision=4)}")
print(f"T(r_w) концов 6:     {np.array2string(tw[lo_end], precision=3)}")
print(f"T(r_w) концов 10.75: {np.array2string(tw[hi_end], precision=3)}")
print(f"T(r_w) по записям: min {tw.min():.3f} (запись {int(np.argmin(tw))}), "
      f"max {tw.max():.3f} (запись {int(np.argmax(tw))})")

# Профили у забоя: конец 29 сут (запись 58, 6 МПа) и 30 сут (запись 60, 10.75 МПа)
for n in (58, 60):
    st = h.states[n]
    print(f"\nзапись {n} ({h.times[n]/DAY:.1f} сут), p_wf = {h.well_data[n].p_wf/1e6:.3f}: "
          f"j | r | p МПа | S_g | R_s | R_s^eq(p) | режим")
    Rs_eq = pvt.Rs_eq(st.p)
    for j in list(range(0, 20)) + [25, 30, 35]:
        print(f"   {j:2d} {r[j]:7.3f} {st.p[j]/1e6:7.4f} {st.Sg[j]:8.5f} {st.Rs[j]:7.3f} "
              f"{min(Rs_eq[j], Rs0):7.3f} {st.regime[j]}")

# report_rs на конце 29 сут (6 МПа) и 30 сут (10.75 МПа)
class _H:
    def __init__(self, states):
        self.states = states


print("\n── report_rs на конце 29 сут (6 МПа) ──")
report_rs(cfg, _H(h.states[:59]), pvt)
print("── report_rs на конце 30 сут (10.75 МПа, финал) ──")
report_rs(cfg, h, pvt)

for npf in (6, 7):
    ts = _profile_times(h.times, npf)
    print(f"n_profiles = {npf}: {[round(t / DAY, 3) for t in ts]} сут")

bal = compute_balance(h, grid, cfg)
print(f"баланс: rel_residual = {float(bal['rel_residual'][-1]):.2e}; "
      f"max по записям {float(np.max(np.abs(bal['rel_residual']))):.2e}")
w = h.well_data[-1]
s = h.states[-1]
print(f"финал: p(r_w) = {s.p[0]/1e6:.4f} МПа, T(r_w) = {s.T[0]:.3f} К, q_o = {w.q_o_std:.4e}, "
      f"q_g = {w.q_g_std:.5f}, max S_g = {s.Sg.max():.5f}, R_s мин = {s.Rs.min():.3f}")

# ── Длительность закрытия после первого (1 -> 2 сут) и последнего (29 -> 30) скачка ──
for n_start, label in ((2, "первый скачок, t = 1 сут"), (58, "последний скачок, t = 29 сут")):
    st1 = h.states[n_start]
    cfg_f = make_cfg([10.75e6], dt_hist=2 * 3600.0, dt_int=60.0)
    sim_f, rec_f, h_f, el_f = run(cfg_f, state=st1)
    first_open = next((x for x in rec_f.rows if x["G_o0"] < 0.0), None)
    n_shut = sum(1 for x in rec_f.rows if x["G_o0"] == 0.0)
    print(f"\n=== {label}: dt = 60 с, 2 ч ({el_f:.1f} с) ===")
    print(f"p[0] в начале {st1.p[0]/1e6:.4f} МПа; подшагов закрыто {n_shut} из {len(rec_f.rows)}")
    if first_open:
        print(f"открылась через {(first_open['t'] - st1.t)/60:.0f} мин "
              f"(p[0] = {first_open['p0']/1e6:.4f} МПа)")

# ── Сверка матрицы энергии (тест DEBT-016) на 13б: время и результат ──
if "--matrix" in sys.argv:
    import test_energy_matrix_examples as tm

    cfg_m = make_cfg(schedule_13b())
    sim_m, init_m = SimulatorFactory.from_config(cfg_m)
    n_calls = [0]

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        ra, rb, rc, rd = tm.build_reference(sim_m._grid, sim_m._pvt, cfg_m.rock,
                                            hydro_result, state_prev, dt, bc)
        for x, y in ((a, ra), (b, rb), (c, rc), (d, rd)):
            np.testing.assert_allclose(x, y, rtol=tm.RTOL, atol=0.0)
        assert a[0] == 0.0 and c[-1] == 0.0
        n_calls[0] += 1

    sim_m._energy.matrix_probe = probe
    t0 = time.perf_counter()
    sim_m.run(init_m)
    print(f"\nсверка матрицы: {n_calls[0]} вызовов, OK, {time.perf_counter() - t0:.1f} с")
