"""FEAT-024 (проработка): охлаждение забоя при R_s0 = 150 и S_gc = 0.1.

Заготовка — конфиг примера 12 (R_ext = 200 м, N = 50, p_wf = 6 МПа).
Меняется:
  - R_s0 = 150 м³ст/м³ст; в oil_pvt.csv ветка R_s = 30 заменена веткой
    R_s = 150 (p_b по умолчанию 15 МПа; B_o, μ_o — живая нефть);
  - ОФП: k_rg = 0 при S_g <= 0.1 (остаточная газонасыщенность 10 %);
  - история: короткие интервалы в начале (шаг растёт геометрически),
    дальше длинные — число подшагов на интервал ceil(dt_hist/dt_integration),
    поэтому короткий интервал = мелкий шаг без правки библиотеки.

Конфиги варианта пишутся в подпапку probes/<имя>/ (CSV рядом с конфигом).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\cooling_probe.py <вариант>
"""

import json
import sys
import time
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

BASE = SOLVER / "examples" / "12_large_drainage_radius"
DAY = 86400.0


def oil_rows(pb, Rs0):
    # Ветка R_s = 0 — как в примере 12; ветка R_s0 — живая нефть:
    # B_o по Стендингу для R_s = 150 ≈ 1.45; ρ_o = (850 + 0.85·150)/1.45 ≈ 674 кг/м³
    return [
        (0.0, 5.0e6, 1.05, 0.003),
        (0.0, 30.0e6, 1.04, 0.0032),
        (Rs0, pb, 1.45, 0.0009),
        (Rs0, 30.0e6, 1.43, 0.00095),
    ]


RELPERM_SGC = [
    # S_g, k_ro, k_rg: k_rg = 0 до S_g = 0.1 включительно
    (0.0, 1.0, 0.0),
    (0.1, 0.8, 0.0),
    (0.2, 0.6, 0.05),
    (0.4, 0.3, 0.2),
    (0.6, 0.1, 0.5),
    (0.8, 0.0, 0.8),
]


def history(t_end_days, p_wf, long_step_days):
    """Интервалы: 1, 1, 2, 4, 8, 8 ч (= 1 сут), 1, 1, 2, 2, 3 сут (= 10 сут), дальше по long_step_days."""
    hours = [1, 1, 2, 4, 8, 8]
    days = [1, 1, 2, 2, 3]
    dts = [h * 3600.0 for h in hours] + [d * DAY for d in days]
    t = sum(dts)
    while t < t_end_days * DAY - 1e-6:
        step = min(long_step_days * DAY, t_end_days * DAY - t)
        dts.append(step)
        t += step
    return [{"dt": dt, "control": "pressure", "p_wf": p_wf} for dt in dts]


def relperm_corey_krg(n_g, S_gc=0.1, S_or=0.2, krg_max=0.8, step=0.01):
    """k_rg по Кори с порогом S_gc на сетке с шагом step; k_ro — из RELPERM_SGC."""
    sg_t = np.array([r[0] for r in RELPERM_SGC])
    kro_t = np.array([r[1] for r in RELPERM_SGC])
    sg = np.round(np.arange(0.0, 0.8 + 1e-9, step), 2)
    krg = krg_max * np.clip((sg - S_gc) / (1 - S_gc - S_or), 0, 1) ** n_g
    return [(float(s), float(np.interp(s, sg_t, kro_t)), float(g)) for s, g in zip(sg, krg)]


def make_variant(name, *, Rs0=150.0, pb=15.0e6, p0=15.5e6, p_wf=6.0e6,
                 t_end_days=30.0, long_step_days=5.0, dt_int=DAY, uniform=None,
                 relperm=RELPERM_SGC):
    d = HERE / name
    d.mkdir(exist_ok=True)
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    cfg["initial_conditions"]["Rs0"] = Rs0
    cfg["initial_conditions"]["p0"] = p0
    cfg["time"]["dt_integration"] = dt_int
    if uniform is not None:
        # uniform = (число интервалов, длина в сутках) — равные интервалы истории
        n, days = uniform
        cfg["time"]["history"] = [{"dt": days * DAY, "control": "pressure", "p_wf": p_wf}
                                  for _ in range(n)]
    else:
        cfg["time"]["history"] = history(t_end_days, p_wf, long_step_days)
    cfg["output"]["log_level"] = "ERROR"
    (d / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(d / "oil_pvt.csv", "w", encoding="utf-8") as f:
        f.write("Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n")
        for r in oil_rows(pb, Rs0):
            f.write(",".join(repr(x) for x in r) + "\n")
    (d / "gas_pvt.csv").write_text((BASE / "gas_pvt.csv").read_text(encoding="utf-8"), encoding="utf-8")
    with open(d / "relperm.csv", "w", encoding="utf-8") as f:
        f.write("Sg,kro,krg\n")
        for r in relperm:
            f.write(",".join(repr(x) for x in r) + "\n")
    return d / "config.json"


class Counting:
    """Обёртка EnergySolver.solve: считает принятые подшаги и их dt."""

    def __init__(self, inner):
        self._inner, self.dts = inner, []

    def solve(self, hr, sp, dt, bc, collect=None):
        self.dts.append(dt)
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def run(cfg_path):
    cfg = load_config(cfg_path)
    sim, init = SimulatorFactory.from_config(cfg)
    cnt = Counting(sim._energy)
    sim._energy = cnt
    t0 = time.perf_counter()
    h = sim.run(init)
    el = time.perf_counter() - t0
    pvt = cnt._inner._pvt
    Rs0 = cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    T0 = cfg.initial_conditions.T0
    r = sim._grid.r_centers
    print(f"\n=== {cfg_path.parent.name}: R_s0 = {Rs0}, p_b = {pb/1e6:.2f} МПа, "
          f"p0 = {cfg.initial_conditions.p0/1e6:.2f}, p_wf = {cfg.time.history[0].p_wf/1e6:.2f}, "
          f"dt_integration = {cfg.time.dt_integration:.0f} с ===")
    print(f"sim.run {el:.1f} с; записей {len(h.states)}; принятых подшагов {len(cnt.dts)}; "
          f"min dt {min(cnt.dts):.3g} с")
    print(f"{'сут':>7} | {'q_o':>10} {'GOR':>7} | {'T_w':>8} {'ΔT_w':>7} {'minT':>8} | "
          f"{'S_g(r_w)':>8} {'maxS_g':>7} | {'n_2ф':>4} {'фронт':>6} | {'p[0]':>7} {'p_N-1-p_b':>9}")
    for n, st in enumerate(h.states):
        w = h.well_data[n]
        tp = np.nonzero(st.Sg > 0)[0]
        g = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
        print(f"{h.times[n]/DAY:7.3f} | {w.q_o_std:10.4e} {g:7.2f} | {st.T[0]:8.3f} "
              f"{st.T[0]-T0:+7.3f} {st.T.min():8.3f} | {st.Sg[0]:8.4f} {st.Sg.max():7.4f} | "
              f"{tp.size:4d} {r[tp[-1]] if tp.size else 0:6.1f} | {st.p[0]/1e6:7.4f} "
              f"{(st.p[-1]-pb)/1e3:+9.1f}")
    bal = compute_balance(h, sim._grid, cfg)
    print(f"баланс энергии: rel_residual = {float(bal['rel_residual'][-1]):.2e}")
    # Профиль T на последней записи — где сосредоточено охлаждение
    st = h.states[-1]
    for rr in (0.1, 0.5, 1, 3, 10, 30, 60, 100, 150):
        j = int(np.argmin(np.abs(r - rr)))
        print(f"   r = {r[j]:7.2f} м: p = {st.p[j]/1e6:7.3f} МПа, S_g = {st.Sg[j]:.4f}, "
              f"T = {st.T[j]:.3f} К ({st.T[j]-T0:+.3f})")
    return h


VARIANTS = {
    # Суточный шаг против часового на первых 30 сут — точность T
    "A30_day": dict(t_end_days=30.0, long_step_days=5.0, dt_int=DAY),
    "A30_hour": dict(t_end_days=30.0, long_step_days=5.0, dt_int=3600.0),
    # Длинный расчёт: 2 года, запись раз в 10 сут
    "A730": dict(t_end_days=730.0, long_step_days=10.0, dt_int=DAY),
    # p_b по Стендингу для R_s = 150 (γ_g = 0.69, 35° API, 350 К) ≈ 23.7 МПа;
    # R_s(p) линейна от 0 при 5 МПа до 150 при 24 МПа; p0 на 0.5 МПа выше p_b
    "B730": dict(pb=24.0e6, p0=24.5e6, t_end_days=730.0, long_step_days=10.0, dt_int=DAY),
    # Решение пользователя 2026-09-30: вариант B, 12 записей по 30 сут.
    # Первый интервал 30 сут — разгона мелкими интервалами нет, проверяем dt_integration
    "B360_day": dict(pb=24.0e6, p0=24.5e6, uniform=(12, 30.0), dt_int=DAY),
    "B360_6h": dict(pb=24.0e6, p0=24.5e6, uniform=(12, 30.0), dt_int=21600.0),
    "B360_hour": dict(pb=24.0e6, p0=24.5e6, uniform=(12, 30.0), dt_int=3600.0),
    # Вопрос пользователя: как поднять S_g у забоя. k_rg по Кори n_g = 3 при том же
    # S_gc = 0.1 (по тождеству Дарси S_g(r_w) ≈ 0.234); разгон — короткими интервалами
    "C360_corey3": dict(pb=24.0e6, p0=24.5e6, t_end_days=360.0, long_step_days=30.0,
                        dt_int=DAY, relperm=relperm_corey_krg(3)),
    # То же на расписании пользователя 12 × 30 сут: сойдётся ли суточный шаг с первого
    # интервала (у линейной k_rg не сходится — B360_day, B360_6h)
    "C360_corey3_day": dict(pb=24.0e6, p0=24.5e6, uniform=(12, 30.0), dt_int=DAY,
                            relperm=relperm_corey_krg(3)),
    # Решение пользователя 2026-09-30: таблица Кори n_g = 3 с шагом 0.05
    # («на практике таблица не бывает очень подробной»); замер на базе после BUG-014
    "D360_corey3_step005": dict(pb=24.0e6, p0=24.5e6, uniform=(12, 30.0), dt_int=DAY,
                                relperm=relperm_corey_krg(3, step=0.05)),
}

if __name__ == "__main__":
    name = sys.argv[1]
    run(make_variant(name, **VARIANTS[name]))
