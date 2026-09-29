"""FEAT-020: числа плана — пример 14 и точность теста согласованности (замер до реализации).

Управления по дебиту в коде ещё нет, поэтому здесь оно подставлено
ВРЕМЕННОЙ заглушкой ProbeRate — это не образец реализации:
  - ProbeRate наследует PressureControl, чтобы пройти isinstance в адаптере;
  - set_bhp_control модели подменён: для ProbeRate вызывается
    set_oil_rate_control(q · 86400, min_bhp / BAR_TO_PA);
  - p_wf для энергии и вывода берётся из model._last_effective_bhp_bar —
    это значение прототип выставил на последнем вызове _well_fluxes,
    то есть в _build_result на состоянии n+1 (то же, что даст
    HydroResult.p_wf по плану). Энергия зовёт boundary_pressure сразу
    после hydro.solve, других вызовов модели между ними нет.

Что замеряется:
  A. Пример 14: конфиг примера 12, 15 интервалов по 86400 с,
     q_k = 18·k м³ст/сут, min_bhp = 1 атм, dt_integration = 3600 с.
     Таблица по записям, дробление шага, срабатывание min_bhp, контурная
     ячейка, баланс энергии, время прогона.
  B. Стационар при q = 270 м³ст/сут: p_wf*, при котором замкнутое
     решение (closed_form.solve_closed) даёт q_o = 270, и отклонение
     профиля 15 сут от него.
  C. Тест согласованности: прогон по давлению (интервал истории = один
     подшаг 3600 с), дебиты его записей подаются расписанием во второй
     прогон по дебиту. Расхождение p, Sg, Rs, T, p_wf по всем записям.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-020\\probes\\plan_numbers.py
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config, HistoryInterval  # noqa: E402
from gpn_multiphase_solver.bc import PressureControl  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
from closed_form import solve_closed  # noqa: E402

BASE = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"
DAY = 86400.0
ATM = 101325.0
Q_LAST = 270.0 / DAY          # м³ст/с


class ProbeRate(PressureControl):
    """Заглушка управления по дебиту — только для замера (см. docstring модуля)."""

    def __init__(self, q_oil, min_bhp, model):
        super().__init__(min_bhp)           # p_wf-заглушка > 0, в расчёт не идёт
        self.q_oil = float(q_oil)
        self.min_bhp = float(min_bhp)
        self._model = model

    def boundary_pressure(self, state, grid, pvt, relperm):
        return self._model._last_effective_bhp_bar * BAR_TO_PA


def enable_rate(simulator, q_list, min_bhp):
    """Подменить управление интервалов на ProbeRate(q_k)."""
    adapter = simulator._hydro
    model = adapter._model
    orig_set = model.set_bhp_control
    cur = {}

    def set_ctrl(bhp_bar):
        w = cur["well"]
        if isinstance(w, ProbeRate):
            model.set_oil_rate_control(w.q_oil * DAY, w.min_bhp / BAR_TO_PA)
        else:
            orig_set(bhp_bar)

    model.set_bhp_control = set_ctrl
    orig_solve = adapter.solve

    def solve(state, dt, bc):
        cur["well"] = bc.well
        return orig_solve(state, dt, bc)

    adapter.solve = solve
    assert len(q_list) == len(simulator._schedule.intervals)
    for iv, q in zip(simulator._schedule.intervals, q_list):
        iv.bc.well = ProbeRate(q, min_bhp, model)
    return model


class LaggedRate(ProbeRate):
    """Мутант для замера чувствительности теста: энергия получает p_wf
    ПРЕДЫДУЩЕГО шага (состояние n вместо n+1) — тонкая ошибка, которую
    главный тест обязан ловить."""

    prev = {}

    def boundary_pressure(self, state, grid, pvt, relperm):
        cur = self._model._last_effective_bhp_bar * BAR_TO_PA
        key = round(state.t, 6)
        if key not in LaggedRate.prev:
            LaggedRate.prev[key] = LaggedRate.prev.get("last", cur)
            LaggedRate.prev["last"] = cur
        return LaggedRate.prev[key]


class Recording:
    """Обёртка EnergySolver.solve: пишет каждый ПРИНЯТЫЙ подшаг."""

    def __init__(self, inner, model):
        self._inner, self._model, self.rows = inner, model, []

    def solve(self, hr, sp, dt, bc, collect=None):
        T_new = self._inner.solve(hr, sp, dt, bc, collect=collect)
        st = hr.state
        self.rows.append(dict(
            t=st.t, dt=dt, p0=st.p[0], pN=st.p[-1], SgN=st.Sg[-1],
            p_wf=bc.well.boundary_pressure(st, None, None, None),
            q_o=-hr.G_o[0], Sg0=st.Sg[0], T0=T_new[0],
            n2=int(np.count_nonzero(st.regime == 1)),
            constraint=bool(self._model._last_constraint_active)))
        return T_new


def build(history, dt_integration=3600.0):
    cfg = load_config(BASE)
    cfg.time.history = history
    cfg.time.dt_integration = dt_integration
    cfg.output.log_level = "WARNING"        # без построчного лога интервалов
    sim, init = SimulatorFactory.from_config(cfg)
    return cfg, sim, init


# ════════════════════════════════════════════════════════════════════
# A. Пример 14
# ════════════════════════════════════════════════════════════════════

def part_a():
    print("═" * 72)
    print("A. Пример 14: q_k = 18·k м³ст/сут, k = 1..15, min_bhp = 1 атм")
    print("═" * 72)
    hist = [HistoryInterval(dt=DAY, control="pressure", p_wf=6e6) for _ in range(15)]
    cfg, sim, init = build(hist)
    q_list = [18.0 * k / DAY for k in range(1, 16)]
    model = enable_rate(sim, q_list, ATM)
    rec = Recording(sim._energy, model)
    sim._energy = rec

    t0 = time.perf_counter()
    history = sim.run(init)
    elapsed = time.perf_counter() - t0

    pvt = rec._inner._pvt
    pb = float(pvt.pb(np.array([cfg.initial_conditions.Rs0]))[0])
    print(f"  sim.run: {elapsed:.1f} с; принятых подшагов энергии: {len(rec.rows)} "
          f"(без дробления было бы 360)")
    dts = sorted({round(r['dt'], 6) for r in rec.rows})
    print(f"  различные dt подшагов: {dts}")
    print(f"  срабатываний min_bhp: {sum(r['constraint'] for r in rec.rows)}")
    print(f"  p_b(Rs0) = {pb / 1e6:.4f} МПа")
    print(f"  контур: min(p[N-1] - p_b) = {min(r['pN'] for r in rec.rows) - pb:+.1f} Па, "
          f"max Sg[N-1] = {max(r['SgN'] for r in rec.rows):.2e}")
    first2 = next((r for r in rec.rows if r['n2'] > 0), None)
    if first2:
        print(f"  первый подшаг с двухфазной ячейкой: t = {first2['t'] / 3600:.0f} ч, "
              f"p_wf = {first2['p_wf'] / 1e6:.4f} МПа")

    print()
    print("  сут | q_o, м³ст/сут | p_wf, МПа | p[0], МПа | GOR   | Sg[0]  | T(r_w), К | 2ф ячеек")
    for k, (t, st, wd) in enumerate(zip(history.times, history.states, history.well_data)):
        gor = wd.q_g_std / wd.q_o_std if wd.q_o_std > 0 else float("nan")
        print(f"  {t / DAY:4.0f} | {wd.q_o_std * DAY:13.4f} | {wd.p_wf / 1e6:9.4f} | "
              f"{st.p[0] / 1e6:9.4f} | {gor:5.1f} | {st.Sg[0]:.4f} | {st.T[0]:9.4f} | "
              f"{int(np.count_nonzero(st.regime == 1)):3d}")

    # Сверка расписания: q_o записи k = q_k с машинной точностью
    q_rec = np.array([w.q_o_std for w in history.well_data[1:]])
    print(f"\n  max|q_o(запись) - q_k| / q_k = "
          f"{np.max(np.abs(q_rec - np.array(q_list)) / np.array(q_list)):.2e}")
    pwf = np.array([r['p_wf'] for r in rec.rows])
    print(f"  p_wf по подшагам монотонно не растёт: {bool(np.all(np.diff(pwf) <= 1e-6))}; "
          f"max приращение = {np.max(np.diff(pwf)):.3e} Па; min p_wf = {pwf.min() / 1e6:.4f} МПа")
    T0s = np.array([r['T0'] for r in rec.rows])
    print(f"  T(r_w): min {T0s.min():.4f} К, в конце {T0s[-1]:.4f} К "
          f"(T0 = {cfg.initial_conditions.T0} К)")

    bal = compute_balance(history, sim._grid, cfg)
    print(f"  баланс энергии: max rel_residual = {np.max(bal['rel_residual'][1:]):.2e}")
    return cfg, sim, history, pvt


# ════════════════════════════════════════════════════════════════════
# B. Стационар при q = 270 м³ст/сут
# ════════════════════════════════════════════════════════════════════

def part_b(cfg, sim, history, pvt):
    print()
    print("═" * 72)
    print("B. Замкнутое стационарное решение при q = 270 м³ст/сут")
    print("═" * 72)
    relperm = _create_relperm(cfg)
    r = sim._grid.r_centers

    def q_of(pwf):
        c = copy.deepcopy(cfg)
        c.time.history[-1].p_wf = pwf
        return solve_closed(c, pvt, relperm, r)["q_o"]

    p0 = cfg.initial_conditions.p0
    t0 = time.perf_counter()
    pwf_star = brentq(lambda x: q_of(x) - Q_LAST, 1.0e6, p0 - 1.0e3, xtol=1.0, rtol=1e-12)
    el = time.perf_counter() - t0
    c = copy.deepcopy(cfg)
    c.time.history[-1].p_wf = pwf_star
    cl = solve_closed(c, pvt, relperm, r)
    print(f"  p_wf* = {pwf_star / 1e6:.5f} МПа (brentq {el:.1f} с); "
          f"q(p_wf*) = {cl['q_o'] * DAY:.6f} м³ст/сут")
    print(f"  q при p_wf = 6 МПа: {q_of(6e6) * DAY:.3f} м³ст/сут; "
          f"при p_wf = 1 атм: {q_of(ATM) * DAY:.3f} м³ст/сут")
    p_num = history.states[-1].p
    wd = history.well_data[-1]
    d = np.abs(cl["p"] - p_num)
    print(f"  расчёт 15 сут: p_wf = {wd.p_wf / 1e6:.5f} МПа; "
          f"max|p_ана - p_чис| = {d.max() / 1e3:.2f} кПа "
          f"({d.max() / (p0 - pwf_star) * 100:.3f} % депрессии)")
    print(f"  Sg макс: {cl['Sg'].max():.5f} (стационар) vs {history.states[-1].Sg.max():.5f} (расчёт)")


# ════════════════════════════════════════════════════════════════════
# C. Тест согласованности
# ════════════════════════════════════════════════════════════════════

def part_c(p_steps, label):
    print()
    print("═" * 72)
    print(f"C. Согласованность управлений: {label}")
    print("═" * 72)
    K = len(p_steps)
    hist = [HistoryInterval(dt=3600.0, control="pressure", p_wf=pw) for pw in p_steps]

    cfg, sim_p, init = build(hist)
    rec_p = Recording(sim_p._energy, sim_p._hydro._model)
    sim_p._energy = rec_p
    t0 = time.perf_counter()
    h_p = sim_p.run(init)
    el_p = time.perf_counter() - t0
    q_list = [w.q_o_std for w in h_p.well_data[1:]]

    cfg2, sim_r, init2 = build(hist)
    model = enable_rate(sim_r, q_list, ATM)
    rec_r = Recording(sim_r._energy, model)
    sim_r._energy = rec_r
    t0 = time.perf_counter()
    h_r = sim_r.run(init2)
    el_r = time.perf_counter() - t0

    print(f"  подшагов энергии: давление {len(rec_p.rows)}, дебит {len(rec_r.rows)} "
          f"(ожидается {K}); время {el_p:.2f} + {el_r:.2f} с")
    print(f"  срабатываний min_bhp: {sum(r['constraint'] for r in rec_r.rows)}")
    print(f"  q: {min(q_list) * DAY:.3f} … {max(q_list) * DAY:.3f} м³ст/сут")
    n2 = max(int(np.count_nonzero(s.regime == 1)) for s in h_p.states)
    print(f"  двухфазных ячеек (макс): {n2}")

    def mx(f):
        return max(float(np.max(np.abs(f(a) - f(b)))) for a, b in zip(h_p.states, h_r.states))

    dp, dSg, dRs, dT = (mx(lambda s: s.p), mx(lambda s: s.Sg),
                        mx(lambda s: s.Rs), mx(lambda s: s.T))
    dpwf = max(abs(a.p_wf - b.p_wf) for a, b in zip(h_p.well_data[1:], h_r.well_data[1:]))
    dq = max(abs(a.q_o_std - b.q_o_std) / a.q_o_std
             for a, b in zip(h_p.well_data[1:], h_r.well_data[1:]))
    dqg = max(abs(a.q_g_std - b.q_g_std) / max(a.q_g_std, 1e-30)
              for a, b in zip(h_p.well_data[1:], h_r.well_data[1:]))
    reg = sum(int(np.count_nonzero(a.regime != b.regime)) for a, b in zip(h_p.states, h_r.states))
    print(f"  max|Δp|    = {dp:.3e} Па")
    print(f"  max|ΔSg|   = {dSg:.3e}")
    print(f"  max|ΔRs|   = {dRs:.3e} м³ст/м³ст")
    print(f"  max|ΔT|    = {dT:.3e} К")
    print(f"  max|Δp_wf| = {dpwf:.3e} Па (давление: уставка; дебит: вычисленное)")
    print(f"  max отн.|Δq_o| = {dq:.2e}, max отн.|Δq_g| = {dqg:.2e}")
    print(f"  несовпадений regime: {reg}")
    bal = compute_balance(h_r, sim_r._grid, cfg2)
    print(f"  баланс энергии (дебит): max rel_residual = {np.max(bal['rel_residual'][1:]):.2e}")

    # Чувствительность: энергия с p_wf предыдущего шага
    cfg3, sim_m, init3 = build(hist)
    model3 = enable_rate(sim_m, q_list, ATM)
    LaggedRate.prev = {}
    for iv, q in zip(sim_m._schedule.intervals, q_list):
        iv.bc.well = LaggedRate(q, ATM, model3)
    h_m = sim_m.run(init3)
    dTm = max(float(np.max(np.abs(a.T - b.T))) for a, b in zip(h_p.states, h_m.states))
    dpm = max(float(np.max(np.abs(a.p - b.p))) for a, b in zip(h_p.states, h_m.states))
    print(f"  мутант «p_wf с запаздыванием на шаг»: max|ΔT| = {dTm:.3e} К, "
          f"max|Δp| = {dpm:.3e} Па (гидродинамика не затронута)")
    # Мутант «уставка вместо фактического»: энергия видит min_bhp
    cfg4, sim_s, init4 = build(hist)
    model4 = enable_rate(sim_s, q_list, ATM)
    for iv in sim_s._schedule.intervals:
        iv.bc.well.boundary_pressure = (lambda *a, _w=iv.bc.well: _w.min_bhp)
    h_s = sim_s.run(init4)
    dTs = max(float(np.max(np.abs(a.T - b.T))) for a, b in zip(h_p.states, h_s.states))
    print(f"  мутант «энергия видит min_bhp»: max|ΔT| = {dTs:.3e} К")


if __name__ == "__main__":
    cfg, sim, history, pvt = part_a()
    part_b(cfg, sim, history, pvt)
    # Сутки при 14.4 МПа — первая ступень 13а, дробления нет (замер FEAT-022)
    part_c([14.4e6] * 24, "24 × 3600 с, p_wf = 14.4 МПа")
    # Со ступенью p_wf внутри прогона
    part_c([14.4e6] * 12 + [13.8e6] * 12, "24 × 3600 с, p_wf = 14.4 → 13.8 МПа на 12 ч")
