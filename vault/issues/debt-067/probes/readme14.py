"""DEBT-067, проба планирования: числа README примера 14 — база и пол округления (вариант a).

База отказывает на первом суточном шаге (условие по ячейке на пределе округления) и
дробит его; с полом первые сутки — одним шагом. Печатает всё, что README 14 цитирует
числами: таблицу записей (q_o, GOR, T(r_w), ΔT, S_g(r_w)), число двухфазных ячеек и фронт,
p − p_b ячейки фронта на 90 сут, min p_{N−1} − p_b, забой на 360 сут, невязку баланса
энергии, число вызовов гидродинамики и отказов.

Запуск из numerical_solver/ (варианты — как в variants.py; по умолчанию base и a;
impl — код каталога запуска без эмуляции, проверка реализации):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-067\\probes\\readme14.py [вариант ...]
Выход — readme14.out.txt (по умолчанию) или readme14_<варианты>.out.txt рядом со скриптом.
"""
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import variants  # noqa: E402  (обёртки Patch, пути SOLVER и прототипа)

from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory, create_pvt   # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError       # noqa: E402
from gpn_multiphase_solver.io.config import load_config                  # noqa: E402

DAY = 86400.0
VARIANTS = sys.argv[1:] or ["base", "a"]
OUT = open(HERE / ("readme14_" + "_".join(sys.argv[1:]) + ".out.txt" if sys.argv[1:]
                   else "readme14.out.txt"), "w", encoding="utf-8")


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


out(f"SOLVER = {SOLVER}, KAPPA = {variants.KAPPA}")
for variant in VARIANTS:
    cfg = load_config(SOLVER / "examples" / "14_high_gor_cooling" / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    variants.Patch(sim._hydro._model, variant)
    calls = []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        try:
            r = orig(state, dt, bc)
        except HydroConvergenceError:
            calls.append((state.t, dt, False))
            raise
        calls.append((state.t, dt, True))
        return r

    sim._hydro.solve = solve
    h = sim.run(init)
    pvt = create_pvt(cfg)
    Rs0 = cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    rc = sim.grid.r_centers
    T0 = cfg.initial_conditions.T0
    fails = [c for c in calls if not c[2]]
    out(f"\n=== {variant}: вызовов гидро {len(calls)}, отказов {len(fails)} "
        f"{[(c[0] / DAY, c[1]) for c in fails]}; первые вызовы {[(c[1], c[2]) for c in calls[:5]]}")
    out("| сут | q_o | GOR | T(r_w), К | ΔT, К | S_g(r_w) | двухфазных | фронт, м |")
    for st, w in zip(h.states[1:], h.well_data[1:]):
        two = np.flatnonzero(st.regime == 1)
        front = rc[two.max()] if two.size else float("nan")
        out(f"| {st.t / DAY:.0f} | {w.q_o_std * 1e3:.4f} | {w.q_g_std / w.q_o_std:.2f} | "
            f"{st.T[0]:.3f} | {st.T[0] - T0:.3f} | {st.Sg[0]:.4f} | {two.size} | {front:.1f} |")
    st90 = h.states[3]
    k = int(np.flatnonzero(st90.regime == 1).max())
    out(f"90 сут: ячейка фронта r = {rc[k]:.1f} м, p − p_b = {(st90.p[k] - pb) / 1e3:+.1f} кПа, "
        f"S_g = {st90.Sg[k]:.2e}")
    out(f"min_t p_(N−1) − p_b = {min(s.p[-1] for s in h.states) / 1e3 - pb / 1e3:+.1f} кПа")
    fin, wf = h.states[-1], h.well_data[-1]
    out(f"360 сут: p(r_w) = {fin.p[0] / 1e6:.3f} МПа, R_s(r_w) = {fin.Rs[0]:.3f}, "
        f"T(r_w) = {fin.T[0]:.3f} К (ΔT = {fin.T[0] - T0:.3f}), S_g(r_w) = {fin.Sg[0]:.4f}, "
        f"q_o = {wf.q_o_std:.4e}, q_g = {wf.q_g_std:.4f}")
    bal = compute_energy_balance(h)
    out(f"баланс энергии: невязка {abs(float(bal['rel_residual'][-1])):.1e}")
