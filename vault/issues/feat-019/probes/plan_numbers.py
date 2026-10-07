"""FEAT-019: числа плана для примера 16 (останов скважины), до реализации.

Конфиг — cfg_16/config.json (make_16_config.py). Конвейер — штатный
run_example (n_profiles = 7, steady_state = False), выход — cfg_16/output.
Дополнительно: обёртка EnergySolver.solve пишет каждый принятый подшаг
(дробление, потоки через забой и контур), баланс массы компонентов по
подшагам, члены баланса энергии на добыче и на останове, таблица по записям.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-019\\probes\\plan_numbers.py
"""

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

import example_runner  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

CFG = HERE / "cfg_16" / "config.json"
DAY = 86400.0
rows = []
_orig_from_config = SimulatorFactory.from_config


class Recording:
    """Обёртка EnergySolver.solve: пишет каждый ПРИНЯТЫЙ подшаг, физику не трогает."""

    def __init__(self, inner):
        self._inner = inner

    def solve(self, hr, sp, dt, bc, collect=None):
        rows.append(dict(t=hr.state.t, dt=dt, G_o0=float(hr.G_o[0]), G_g0=float(hr.G_g[0]),
                         G_oN=float(hr.G_o[-1]), G_gN=float(hr.G_g[-1]), p0=float(hr.state.p[0]),
                         n2=int(np.count_nonzero(hr.state.regime == 1))))
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def from_config(config):
    sim, init = _orig_from_config(config)
    sim._energy = Recording(sim._energy)
    return sim, init


example_runner.SimulatorFactory.from_config = staticmethod(from_config)

t0 = time.perf_counter()
elapsed, h, grid, cfg = example_runner.run_example(
    CFG, HERE / "cfg_16" / "output", "16: останов скважины после 15 сут добычи",
    n_profiles=7, steady_state=False)
print(f"\n=== main: {time.perf_counter() - t0:.1f} с, расчёт {elapsed:.1f} с ===")

pvt = SimulatorFactory.from_config(cfg)[0]._energy._pvt
Rs0 = cfg.initial_conditions.Rs0
pb = float(pvt.pb(np.array([Rs0]))[0])
r = grid.r_centers
tt = np.array(h.times) / DAY
print(f"записей {len(h.states)}; интервалов {len(cfg.time.history)}; p_b = {pb/1e6:.4f} МПа")
print(f"принятых подшагов {len(rows)}; dt: {dict(sorted(Counter(round(x['dt'], 1) for x in rows).items()))}")
sub = Counter(round(x["t"] / 3600.0, 2) for x in rows if x["dt"] < 3600.0 - 1e-9)
print(f"мелкие подшаги (момент конца, ч): {dict(sub)}")
t_shut = 15 * DAY
sh = [x for x in rows if x["t"] > t_shut + 1e-6]
print(f"останов: подшагов {len(sh)}, max|G_o[0]| = {max(abs(x['G_o0']) for x in sh):.3e}, "
      f"max|G_g[0]| = {max(abs(x['G_g0']) for x in sh):.3e}; приток через контур G_o[N]: "
      f"первый {sh[0]['G_oN']:.3e}, последний {sh[-1]['G_oN']:.3e} м³ст/с")

phiV = cfg.rock.porosity * grid.volumes


def masses(st):
    Bo, Bg = pvt.Bo(st.p, st.Rs), pvt.Bg(st.p)
    So = 1.0 - st.Sg
    return np.sum(phiV * So / Bo), np.sum(phiV * (So * st.Rs / Bo + st.Sg / Bg))


mo0, mg0 = masses(h.states[0])
mo1, mg1 = masses(h.states[-1])
fo = sum(x["dt"] * (x["G_o0"] - x["G_oN"]) for x in rows)
fg = sum(x["dt"] * (x["G_g0"] - x["G_gN"]) for x in rows)
po = -sum(x["dt"] * x["G_o0"] for x in rows)
pg = -sum(x["dt"] * x["G_g0"] for x in rows)
print(f"баланс массы: нефть {(mo1 - mo0 - fo)/po:.2e}, газ {(mg1 - mg0 - fg)/pg:.2e} (доля добычи)")

# ── Таблица по записям ──
print(f"\n{'n':>3} {'t, сут':>8} | {'p_wf':>7} {'q_o':>10} {'q_g':>10} | {'p[0]':>7} {'T_w':>8} "
      f"{'S_g(r_w)':>8} {'n_2ф':>4} | {'Rs(r_w)':>7} {'недонас':>7}")
for n, st in enumerate(h.states):
    w = h.well_data[n]
    und = int(np.count_nonzero((st.regime == 2) & (st.Rs < Rs0 - 1e-9)))
    print(f"{n:3d} {tt[n]:8.4f} | {w.p_wf/1e6:7.4f} {w.q_o_std:10.3e} {w.q_g_std:10.3e} | "
          f"{st.p[0]/1e6:7.4f} {st.T[0]:8.4f} {st.Sg[0]:8.5f} {int(np.count_nonzero(st.regime == 1)):4d} | "
          f"{st.Rs[0]:7.3f} {und:7d}")

# ── Монотонность p(r_w) и T(r_w) на останове ──
k15 = int(np.argmin(np.abs(tt - 15.0)))
pw = np.array([s.p[0] for s in h.states])
tw = np.array([s.T[0] for s in h.states])
d = np.diff(pw[k15:])
print(f"\nзапись конца добычи: {k15} (t = {tt[k15]:.4f}); p(r_w) на останове: min шаг {d.min():.3e} Па, "
      f"неубывает: {bool(np.all(d >= 0))}")
kmax = k15 + int(np.argmax(tw[k15:]))
print(f"T(r_w): конец добычи {tw[k15]:.4f}, max на останове {tw[kmax]:.4f} (запись {kmax}, "
      f"{tt[kmax]:.4f} сут), финал {tw[-1]:.4f}; после max убывает: {bool(np.all(np.diff(tw[kmax:]) <= 0))}")
cross = next(n for n in range(k15, len(pw)) if pw[n] > pb)
print(f"p(r_w) > p_b с записи {cross} (t = {tt[cross]:.4f} сут, p = {pw[cross]/1e6:.4f})")
first_1ph = next((n for n in range(k15, len(h.states))
                  if np.count_nonzero(h.states[n].regime == 1) == 0), None)
print(f"все ячейки однофазны с записи {first_1ph} (t = {tt[first_1ph]:.4f} сут)" if first_1ph
      else "двухфазные ячейки остаются до конца")

# ── Финальный профиль ──
st = h.states[-1]
rs_sat = pvt.Rs_eq(st.p)
print(f"\nфинал: p ∈ [{st.p.min()/1e6:.5f}, {st.p.max()/1e6:.5f}] МПа; S_g max {st.Sg.max():.3e}; "
      f"R_s ∈ [{st.Rs.min():.4f}, {st.Rs.max():.4f}]; max(R_s - R_s,нас) = {np.max(st.Rs - rs_sat):.3e}")
for j in (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 49):
    print(f"   j={j:2d} r={r[j]:8.3f}  R_s={st.Rs[j]:7.3f}  T={st.T[j]:8.4f}")

# ── Числа для тестов класса примера 16 ──
p_ext = cfg.initial_conditions.p0
print(f"\nфинал: max|p - p_ext| = {np.max(np.abs(st.p - p_ext)):.3e} Па; "
      f"R_s монотонно не убывает по r: {bool(np.all(np.diff(st.Rs) >= 0))}")
k20 = int(np.argmin(np.abs(tt - 20.0)))
print(f"max|R_s(20 сут) - R_s(30 сут)| = {np.max(np.abs(h.states[k20].Rs - st.Rs)):.3e}; "
      f"max|R_s(16 сут) - R_s(30 сут)| = {np.max(np.abs(h.states[39].Rs - st.Rs)):.3e}")
wd = h.well_data
print(f"останов: max|p_wf(WellData) - p[0]| = "
      f"{max(abs(wd[n].p_wf - h.states[n].p[0]) for n in range(16, len(wd))):.3e} Па; "
      f"q_o == 0 и q_g == 0 точно: {all(wd[n].q_o_std == 0.0 and wd[n].q_g_std == 0.0 for n in range(16, len(wd)))}")
print(f"T(r_w) записей 15, 16, 17, 18: {[round(float(tw[n]), 4) for n in (15, 16, 17, 18)]}")
print(f"S_g max по истории {max(float(s.Sg.max()) for s in h.states):.5f} (запись "
      f"{int(np.argmax([s.Sg.max() for s in h.states]))}); q_o[15] = {wd[15].q_o_std:.4e}, "
      f"q_g[15] = {wd[15].q_g_std:.4e}")

# ── Члены баланса энергии: добыча и останов ──
bal = compute_balance(h, grid, cfg)
keys = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")
print(f"\nбаланс энергии: rel_residual финал {float(bal['rel_residual'][-1]):.2e}, "
      f"max {float(np.max(np.abs(bal['rel_residual']))):.2e}")
for k in keys:
    a = float(bal[k][k15]) - float(bal[k][0])
    b = float(bal[k][-1]) - float(bal[k][k15])
    c = float(bal[k][k15 + 24]) - float(bal[k][k15])
    print(f"   {k:10s}: добыча {a:+.4e}, останов {b:+.4e} (из них 1-е сутки {c:+.4e}) Дж")
