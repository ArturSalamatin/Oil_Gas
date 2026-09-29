"""FEAT-022: числа плана для примеров 13а и 13б (замер до реализации).

Конфиг — пример 12 (R_ext = 200 м, p0 = 15.5 МПа, p_b = 15 МПа, N = 50),
меняется только time.history:
  13а — 30 интервалов по 43200 с, p_wf = 15 - 0.6·k МПа на сутках k = 1..15;
  13б — 60 интервалов по 43200 с, нечётные сутки 6 МПа, чётные 10.75 МПа.
dt_integration = 3600 с, как в 12.

Что замеряется:
  - дробление шага (A-retry) — по вызовам EnergySolver.solve, как в
    test_energy_substeps_preserve_total_time;
  - закрытие скважины: принятые подшаги с G_o[0] = 0 (прототип при
    p[0] <= p_wf закрывает скважину, blackoil.py:78-88);
  - возврат ячеек в однофазный режим (regime 1 -> 2) и недонасыщенная
    нефть ниже p_b(R_s0);
  - таблица по записям: p_wf, q_o, GOR, T(r_w), S_g(r_w), число
    двухфазных ячеек;
  - баланс энергии, время прогона;
  - 13б: длительность закрытия после первого скачка 6 -> 10.75 МПа
    при мелком шаге (60 с).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\plan_numbers.py
"""

import copy
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
from closed_form import solve_closed  # noqa: E402
from gpn_multiphase_solver.factory import _create_relperm  # noqa: E402

BASE = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"
HALF_DAY = 43200.0


class Recording:
    """Обёртка EnergySolver.solve: пишет каждый ПРИНЯТЫЙ подшаг, физику не трогает."""

    def __init__(self, inner):
        self._inner, self.rows = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        st = hr.state
        self.rows.append(dict(
            t=st.t, dt=dt, G_o0=float(hr.G_o[0]), p0=float(st.p[0]),
            p_wf=float(bc.well.p_wf), n2=int(np.count_nonzero(st.regime == 1)),
            regime=st.regime.copy(), regime_prev=sp.regime.copy()))
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def schedule_13a():
    # Сутки k = 1..15: p_wf = 15 - 0.6·k МПа, по два интервала 0.5 сут
    return [15.0e6 - 0.6e6 * k for k in range(1, 16) for _ in range(2)]


def schedule_13b():
    # Сутки 1..30: нечётные 6 МПа, чётные 10.75 МПа
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
    try:
        h = sim.run(init if state is None else state)
    except RuntimeError as e:
        # Отказ гидродинамики: где именно — последний принятый подшаг
        last = rec.rows[-1] if rec.rows else None
        print(f"\nОТКАЗ через {time.perf_counter() - t0:.1f} с: {str(e)[:100]}")
        if last:
            print(f"последний принятый подшаг: t = {last['t']/86400:.4f} сут "
                  f"({last['t']:.0f} с), dt = {last['dt']:.2f} с, p_wf = {last['p_wf']/1e6:.3f}, "
                  f"p[0] = {last['p0']/1e6:.4f} МПа, n_2ф = {last['n2']}")
            for x in rec.rows[-6:]:
                print(f"   t = {x['t']:.0f} с, dt = {x['dt']:.2f}, G_o[0] = {x['G_o0']:+.3e}, "
                      f"p[0] = {x['p0']/1e6:.4f}, p_wf = {x['p_wf']/1e6:.3f}")
        raise
    return sim, rec, h, time.perf_counter() - t0


def report(name, cfg, sim, rec, h, el):
    grid, pvt = sim._grid, rec._inner._pvt
    Rs0 = cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    r = grid.r_centers
    dts = Counter(round(x["dt"], 3) for x in rec.rows)
    print(f"\n=== {name}: {len(cfg.time.history)} × {cfg.time.history[0].dt:.0f} с, "
          f"dt_integration = {cfg.time.dt_integration:.0f} с ===")
    print(f"sim.run {el:.1f} с; записей {len(h.states)}; принятых подшагов {len(rec.rows)}; "
          f"dt: {dict(dts)}; сумма dt {sum(x['dt'] for x in rec.rows):.0f} с")

    # Дробление по интервалам: где dt < dt_integration
    sub = Counter()
    for x in rec.rows:
        if x["dt"] < cfg.time.dt_integration - 1e-9:
            sub[int((x["t"] - 1e-6) // 86400) + 1] += 1
    print(f"сутки с дроблением (сутки: число мелких подшагов): {dict(sub)}")

    # Закрытие скважины: принятые подшаги с G_o[0] == 0
    shut = [x for x in rec.rows if x["G_o0"] == 0.0]
    print(f"подшагов с закрытой скважиной (G_o[0] = 0): {len(shut)}")
    for x in shut[:12]:
        print(f"   t = {x['t']/86400:8.4f} сут, dt = {x['dt']:8.2f} с, p[0] = {x['p0']/1e6:.4f} МПа, "
              f"p_wf = {x['p_wf']/1e6:.3f}")
    pos = [x for x in rec.rows if x["G_o0"] > 0.0]
    print(f"подшагов с G_o[0] > 0 (закачка): {len(pos)}")

    # Переходы regime 1 -> 2 (двухфазная -> однофазная) на принятых подшагах
    back = [(x["t"], int(np.count_nonzero((x["regime_prev"] == 1) & (x["regime"] == 2))))
            for x in rec.rows]
    back = [(t, n) for t, n in back if n > 0]
    print(f"подшагов с переходом ячеек 1 -> 2: {len(back)}; всего переходов "
          f"{sum(n for _, n in back)}")
    for t, n in back[:8]:
        print(f"   t = {t/86400:8.4f} сут: {n} ячеек")

    print(f"{'сут':>5} | {'p_wf':>6} | {'q_o':>10} {'GOR':>7} | {'T_w':>8} {'S_g(r_w)':>8} | "
          f"{'n_2ф':>4} {'фронт':>6} | {'p[0]':>7} | {'недонас.':>8}")
    for n, st in enumerate(h.states):
        w = h.well_data[n]
        tp = np.nonzero(st.Sg > 0)[0]
        g = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
        # недонасыщенная нефть ниже p_b(R_s0): однофазная ячейка с p < p_b
        und = int(np.count_nonzero((st.regime == 2) & (st.p < pb)))
        print(f"{h.times[n]/86400:5.1f} | {w.p_wf/1e6:6.3f} | {w.q_o_std:10.4e} {g:7.2f} | "
              f"{st.T[0]:8.3f} {st.Sg[0]:8.4f} | {tp.size:4d} {r[tp[-1]] if tp.size else 0:6.1f} | "
              f"{st.p[0]/1e6:7.4f} | {und:8d}")

    print(f"контур: min p_N-1 - p_b = {(min(s.p[-1] for s in h.states) - pb)/1e3:+.1f} кПа; "
          f"max S_g,N-1 = {max(s.Sg[-1] for s in h.states):.1e}")
    bal = compute_balance(h, grid, cfg)
    print(f"баланс: rel_residual = {float(bal['rel_residual'][-1]):.2e}; "
          f"max по записям {float(np.max(bal['rel_residual'])):.2e}")
    return pb


# ── 13а ──
cfg_a = make_cfg(schedule_13a())
sim_a, rec_a, h_a, el_a = run(cfg_a)
report("13а", cfg_a, sim_a, rec_a, h_a, el_a)

# Замкнутое решение при p_wf последнего интервала (решение 8) против 15 сут
cfg_cl = copy.deepcopy(cfg_a)
cfg_cl.time.history[0].p_wf = cfg_a.time.history[-1].p_wf
cl = solve_closed(cfg_cl, sim_a._energy._inner._pvt, _create_relperm(cfg_cl),
                  sim_a._grid.r_centers)
q15 = h_a.well_data[-1].q_o_std
print(f"замкнутое решение при p_wf = {cfg_cl.time.history[0].p_wf/1e6:.1f} МПа: "
      f"q_o = {cl['q_o']:.4e} (расчёт на 15 сут {q15:.4e}), r_b = {cl['r_b']:.2f} м, "
      f"max S_g = {cl['Sg'].max():.4f}")

# ── 13а: числа для README (то, что напечатает run_example после правки
#    closed_form на p_wf последнего интервала) ──
from rs_analytics import report_rs  # noqa: E402
from closed_form import report_closed  # noqa: E402
from temperature_asymptotics import report_asymptotics  # noqa: E402

pvt_a = sim_a._energy._inner._pvt
s15 = h_a.states[-1]
w15 = h_a.well_data[-1]
bal_a = compute_balance(h_a, sim_a._grid, cfg_a)
print(f"\nзабой 15 сут: p = {s15.p[0]/1e6:.3f} МПа, R_s = {s15.Rs[0]:.3f}, T = {s15.T[0]:.3f} К "
      f"(ΔT = {s15.T[0] - cfg_a.initial_conditions.T0:+.3f}), q_o = {w15.q_o_std:.4e}, "
      f"q_g = {w15.q_g_std:.5f}")
print(f"E_конд = {float(np.ravel(bal_a['cum_cond'])[-1]):+.3e} Дж")
print()
report_rs(cfg_a, h_a, pvt_a)
print()
report_closed(cfg_cl, h_a, sim_a._grid, sim_a)
print()
sim_a._energy = sim_a._energy._inner      # report_asymptotics берёт simulator._energy
report_asymptotics(cfg_a, h_a, sim_a._grid, sim_a)

# ── 13б ──
cfg_b = make_cfg(schedule_13b())
try:
    sim_b, rec_b, h_b, el_b = run(cfg_b)
except RuntimeError:
    print("13б: отказ гидродинамики — см. upstep_diag.py, retries_cost.py")
    sys.exit(0)
report("13б", cfg_b, sim_b, rec_b, h_b, el_b)

# ── 13б: длительность закрытия после первого скачка вверх, шаг 60 с ──
# Состояние конца 1-х суток (запись 2: 0.5 и 1.0 сут) — стартовое;
# 3 ч при 10.75 МПа с dt_integration = 60 с.
st1 = h_b.states[2]
cfg_f = make_cfg([10.75e6], dt_hist=3 * 3600.0, dt_int=60.0)
sim_f, rec_f, h_f, el_f = run(cfg_f, state=st1)
first_open = next((x for x in rec_f.rows if x["G_o0"] < 0.0), None)
n_shut = sum(1 for x in rec_f.rows if x["G_o0"] == 0.0)
print(f"\n=== 13б, первый скачок 6 -> 10.75 МПа, dt = 60 с, 3 ч ({el_f:.1f} с) ===")
print(f"p[0] в начале: {st1.p[0]/1e6:.4f} МПа; подшагов закрыто: {n_shut} из {len(rec_f.rows)}")
if first_open:
    print(f"скважина открылась через {(first_open['t'] - st1.t)/60:.1f} мин "
          f"(p[0] = {first_open['p0']/1e6:.4f} МПа)")
for x in rec_f.rows[:: max(1, len(rec_f.rows) // 12)]:
    print(f"   {(x['t'] - st1.t)/60:6.1f} мин: G_o[0] = {x['G_o0']:+.3e}, "
          f"p[0] = {x['p0']/1e6:.4f} МПа, n_2ф = {x['n2']}")
