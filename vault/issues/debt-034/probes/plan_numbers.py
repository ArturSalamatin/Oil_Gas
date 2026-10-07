"""DEBT-034: числа README и тестов примера 20 (R_s0 = 300) на конфиге examples/20_rs300_cooling.

Замеряется (логика tests/test_examples.py::TestStandingCoreyCooling):
  - таблица по всем записям (часовые 0..2 сут, суточные 3..30 сут): q_o, GOR, T(r_w), ΔT,
    S_g(r_w), R_s(r_w), p[0], число двухфазных ячеек и их дальность, p_{N-1} - p_b;
  - ΔT(r_w) по всем записям 1..N и только по суточным; T_well, S_g(r_w) на 30 сут;
  - GOR: строгий рост и GOR < R_s0 — по всем записям и по суточным;
  - контур: min_t (p_{N-1} - p_b), max S_g[N-1], max |R_s[N-1] - R_s0|;
  - газ и давление (test_gas_active_cells_match_pressure);
  - профиль на 30 сут; баланс энергии (члены и невязка);
  - число подшагов и наименьший шаг, время sim.run;
  - тот же расчёт с thermal.L_degas = 0 — вклад теплоты выделения газа в ΔT(r_w);
  - оценка М.3 (изоэнтальпийный баланс, GOR = R_s0) по вкладам.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-034\\probes\\plan_numbers.py
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
from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

DAY = 86400.0
CONFIG = SOLVER / "examples" / "20_rs300_cooling" / "config.json"
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


def run(L_degas=None):
    """Расчёт примера 20; L_degas — замена thermal.L_degas (None — как в конфиге)."""
    cfg = load_config(CONFIG)
    cfg.output.log_level = "ERROR"
    if L_degas is not None:
        cfg.thermal.L_degas = L_degas
    sim, init = SimulatorFactory.from_config(cfg)
    cnt = Counting(sim._energy)
    sim._energy = cnt
    t0 = time.perf_counter()
    h = sim.run(init)
    return cfg, sim, cnt, h, time.perf_counter() - t0


def m3(cfg):
    """Оценка М.3 на 1 м³ст нефти, путь p0 -> p_wf, GOR = R_s0 (как feat-025/probes/m3_estimate.py)."""
    ic, pc, tc = cfg.initial_conditions, cfg.pvt, cfg.thermal
    pvt = StandingFullPVT(pc.rho_o_std, pc.rho_g_std, ic.T0, ic.Rs0)
    p0, pw = ic.p0, cfg.time.history[-1].p_wf
    rg, ro, Rs0 = pc.rho_g_std, pc.rho_o_std, ic.Rs0
    ps = np.linspace(p0, pw, 4001)
    rs = np.minimum(pvt.Rs_eq(ps), Rs0)
    a = b = c = 0.0
    for i in range(len(ps) - 1):
        dp = ps[i + 1] - ps[i]
        r = 0.5 * (rs[i] + rs[i + 1])
        mo, mg = ro + r * rg, (Rs0 - r) * rg
        C = mo * tc.c_p_oil + mg * tc.c_p_gas
        a += mo * tc.c_p_oil * tc.mu_JT_oil * dp / C
        b += mg * tc.c_p_gas * tc.mu_JT_gas * dp / C
        c += -tc.L_degas * (rs[i] - rs[i + 1]) * rg / C
    xg = (Rs0 - rs[-1]) * rg / (ro + Rs0 * rg)
    return a, b, c, xg, rs[-1]


def main():
    cfg, sim, cnt, h, el = run()
    grid, pvt = sim._grid, cnt._inner._pvt
    r = grid.r_centers
    T0, Rs0 = cfg.initial_conditions.T0, cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    t_day = np.asarray(h.times) / DAY
    print(f"p_b = {pb/1e6:.4f} МПа, p0 = {cfg.initial_conditions.p0/1e6} МПа, "
          f"p0 - p_b = {(cfg.initial_conditions.p0 - pb)/1e6:.4f} МПа, N = {cfg.grid.N}, "
          f"L = {cfg.thermal.L_degas/1e3:.0f} кДж/кг")
    print(f"sim.run {el:.1f} с; подшагов {len(cnt.dts)} (интервалов {len(cfg.time.history)}), "
          f"min dt {min(cnt.dts):.0f} с; записей {len(h.states)}")

    print(f"{'сут':>7} | {'q_o,1e-3':>9} {'GOR':>7} | {'T_w':>8} {'ΔT':>7} | "
          f"{'Sg_w':>6} {'Rs_w':>7} {'p0,МПа':>7} | {'2ф':>3} {'дальн':>6} | {'pN-pb,кПа':>9}")
    margins = []
    for n, st in enumerate(h.states):
        w = h.well_data[n]
        g = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
        tp = np.flatnonzero(st.Sg > 0)
        far = r[tp[-1]] if tp.size else 0.0
        margins.append(st.p[-1] - pb)
        print(f"{t_day[n]:7.3f} | {w.q_o_std*1e3:9.4f} {g:7.2f} | "
              f"{st.T[0]:8.3f} {st.T[0]-T0:+7.3f} | {st.Sg[0]:6.4f} {st.Rs[0]:7.3f} "
              f"{st.p[0]/1e6:7.4f} | {tp.size:3d} {far:6.1f} | {(st.p[-1]-pb)/1e3:9.1f}")

    print(f"контур: min_t (p_N-1 - p_b) = {min(margins)/1e3:+.1f} кПа; "
          f"max S_g[N-1] = {max(st.Sg[-1] for st in h.states):.3e}; "
          f"max |R_s[N-1] - R_s0| = {max(abs(st.Rs[-1]-Rs0) for st in h.states):.3e}")

    # Записи 1..N и только суточные (t кратно 1 сут, t > 0)
    idx_all = np.arange(1, len(h.states))
    idx_day = np.array([n for n in idx_all if abs(t_day[n] - round(t_day[n])) < 1e-9])
    qo = np.array([w.q_o_std for w in h.well_data])
    qg = np.array([w.q_g_std for w in h.well_data])
    Tw = np.array([st.T[0] for st in h.states])
    for tag, idx in (("все записи", idx_all), ("суточные", idx_day)):
        gor = qg[idx] / qo[idx]
        dT = Tw[idx] - T0
        dg = np.diff(gor)
        print(f"[{tag}, {idx.size}] ΔT(r_w): от {dT.max():+.3f} до {dT.min():+.3f} К; "
              f"GOR {gor[0]:.2f} → {gor[-1]:.2f}, строго растёт: {bool(np.all(dg > 0))}, "
              f"min ΔGOR = {dg.min():.4f}, все < R_s0: {bool(np.all(gor < Rs0))}")
        if not np.all(dg > 0):
            bad = idx[1:][dg <= 0]
            print(f"   GOR не растёт на записях t = {[round(float(t_day[k]), 3) for k in bad]}")
    print(f"T_well(30) = {Tw[-1]:.3f} К; ΔT = {Tw[-1]-T0:+.3f} К; S_g(r_w, 30) = {h.states[-1].Sg[0]:.4f}")

    # Свойства при p_b и состав потока у забоя на 30 сут
    pc = cfg.pvt
    Bo_b = float(pvt.Bo(np.array([pb]), np.array([Rs0]))[0])
    mu_b = float(pvt.mu_o(np.array([pb]), np.array([Rs0]))[0])
    gor30, rsw30 = qg[-1] / qo[-1], h.states[-1].Rs[0]
    # Доля свободного газа по массе в потоке у забоя: (GOR - R_s(r_w)) ρ_g / (ρ_o + GOR ρ_g)
    xg30 = (gor30 - rsw30) * pc.rho_g_std / (pc.rho_o_std + gor30 * pc.rho_g_std)
    print(f"B_o(p_b) = {Bo_b:.3f}; mu_o(p_b) = {mu_b*1e3:.3f} мПа·с; "
          f"q_o(30) = {qo[-1]*DAY:.0f} м³ст/сут; доля свободного газа у забоя на 30 сут = {xg30:.3f}")
    from rs_analytics import rs_error
    print(f"проверка R_s: (max_abs, max_rel) = {rs_error(cfg, h, pvt)}")
    dq_o, dq_g = np.diff(qo[1:]), np.diff(qg[1:])
    print(f"q_o строго убывает: {bool(np.all(dq_o < 0))}; q_g монотонен: "
          f"{bool(np.all(dq_g > 0)) or bool(np.all(dq_g < 0))} "
          f"(растёт на {int(np.sum(dq_g > 0))}, убывает на {int(np.sum(dq_g < 0))} интервалах)")
    # Стартовая S_g «закрытого сосуда» у забоя (README, абзац «Сходимость»; BUG-018):
    # S_g = d B_g / (B_o + d B_g), d = R_s0 - R_s(p_wf)
    pw = np.array([cfg.time.history[0].p_wf])
    rs_w = pvt.Rs_eq(pw)
    d = Rs0 - float(rs_w[0])
    Bg_w, Bo_w = float(pvt.Bg(pw)[0]), float(pvt.Bo(pw, rs_w)[0])
    print(f"закрытый сосуд при p_wf: d = {d:.1f}, S_g = {d*Bg_w/(Bo_w + d*Bg_w):.3f}; "
          f"1 - S_or = {1 - cfg.relperm.S_or:.2f}")

    ok1 = ok2 = ok3 = True
    worst_above, n_above = np.inf, 0
    for st in h.states:
        below = st.p < pb
        two = st.regime == 1
        ok1 &= bool(np.array_equal(st.Sg > 0.0, two))
        ok2 &= bool(np.all(two[below]))
        above = two & ~below
        if above.any():
            n_above += 1
            worst_above = min(worst_above, float(st.Sg[above].min()))
            ok3 &= bool(np.all(st.Sg[above] > 1e-8))
    print(f"газ/давление: S_g>0 <=> regime=1: {ok1}; p<p_b => 2ф: {ok2}; "
          f"2ф при p>=p_b только с S_g>1e-8: {ok3} (записей с такими ячейками {n_above}, "
          f"min S_g {worst_above:.3e})")

    # Зона нагрева: max ΔT по всем ячейкам — на 30 сут и по всем записям (аудит плана)
    dT_cells = np.array([st.T - T0 for st in h.states[1:]])
    n_hot, j_hot = np.unravel_index(np.argmax(dT_cells), dT_cells.shape)
    print(f"max ΔT по ячейкам: на 30 сут {dT_cells[-1].max():+.4f} К "
          f"(r = {r[int(np.argmax(dT_cells[-1]))]:.2f} м); по всем записям "
          f"{dT_cells.max():+.4f} К (t = {t_day[n_hot + 1]:.3f} сут, r = {r[j_hot]:.2f} м)")

    st = h.states[-1]
    print(f"профиль на {t_day[-1]:.0f} сут:")
    for rr in R_PROFILE:
        j = int(np.argmin(np.abs(r - rr)))
        print(f"   r = {r[j]:7.2f} м: p = {st.p[j]/1e6:7.3f} МПа, S_g = {st.Sg[j]:.4f}, "
              f"ΔT = {st.T[j]-T0:+.3f} К")

    bal = compute_balance(h, grid, cfg)
    print(f"баланс энергии: rel_residual = {bal['rel_residual'][-1]:.2e}")
    for k, v in bal.items():
        if k != "rel_residual" and np.ndim(v) == 1 and len(v) == len(h.states):
            print(f"   {k}: {v[-1]:.4e}")

    a, b, c, xg, rsw = m3(cfg)
    print(f"М.3: ΔT_w = {a+b+c:+.2f} К (нефть {a:+.2f}, газ {b:+.2f}, L {c:+.2f}); "
          f"R_s(p_wf) = {rsw:.1f}; доля газа в потоке у забоя x_g = {xg:.3f}; "
          f"расчёт/оценка на 30 сут = {(Tw[-1]-T0)/(a+b+c)*100:.0f} %")

    _, _, _, h0, el0 = run(L_degas=0.0)
    T0w = h0.states[-1].T[0]
    print(f"L = 0: T_well(30) = {T0w:.3f} К, ΔT = {T0w-T0:+.3f} К; вклад L = "
          f"{Tw[-1]-T0w:+.3f} К; чувствительность {(Tw[-1]-T0w)/(cfg.thermal.L_degas/1e3):+.4f} К "
          f"на кДж/кг; sim.run {el0:.1f} с")


if __name__ == "__main__":
    main()
