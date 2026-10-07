"""Аудит FEAT-023, шаги 4-5 плана: проверка конфига и тела тестов класса Q.

Конфиг — cfg_13b/config.json (собран run_example_13b.py тем же выражением,
что генератор плана make_13b_config.py). Печатается строка проверки шага 4.1
и выполняются тела шести тестов TestPwfAlternating на свежем расчёте —
с теми же фикстурными полями, что даёт tests/test_examples.py::_run.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-023\\probes\\audit_tests_13b.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.factory import SimulatorFactory, _create_pvt  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CFG = HERE / "cfg_13b" / "config.json"
BASE = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"

# ── Шаг 4.1: строка проверки и отличие от 12 только в time.history ──
c = json.load(open(CFG, encoding="utf-8"))
h = c["time"]["history"]
print(len(h), sum(x["dt"] for x in h) / 86400, h[0]["p_wf"], h[1]["p_wf"], h[2]["p_wf"],
      h[-1]["p_wf"], c["time"]["dt_integration"], c["geometry"]["R_ext"],
      c["initial_conditions"]["p0"], c["grid"]["N"])
b = json.load(open(BASE, encoding="utf-8"))
diff = [k for k in set(c) | set(b) if c.get(k) != b.get(k)]
tdiff = [k for k in set(c["time"]) | set(b["time"]) if c["time"].get(k) != b["time"].get(k)]
print("разделы, отличные от 12:", diff, "; в time:", tdiff)

# ── Расчёт, как _run в test_examples.py ──
cfg = load_config(CFG)
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
t0 = time.perf_counter()
history = sim.run(init)
print(f"sim.run {time.perf_counter() - t0:.1f} с")
r = {"history": history, "config": cfg, "Rs0": cfg.initial_conditions.Rs0,
     "q_o": np.array([w.q_o_std for w in history.well_data])}


def pwf_of_day(d):
    return 6.0e6 if d % 2 == 1 else 10.75e6


# test_pwf_follows_schedule
wd = history.well_data
assert len(wd) == 61
dev = max(abs(wd[n].p_wf - pwf_of_day((n + 1) // 2)) for n in range(1, 61))
assert dev < 1e-3
print(f"OK test_pwf_follows_schedule (max откл. {dev:.3e} Па)")

# test_high_pwf_days_produce_less
q = r["q_o"]
sg_w = np.array([st.Sg[0] for st in history.states])
for k in range(1, 16):
    lo, hi = 4 * k - 2, 4 * k
    assert q[hi] < q[lo] and sg_w[hi] < sg_w[lo], k
print(f"OK test_high_pwf_days_produce_less: q_o 10.75 {q[4::4].min():.4e}..{q[4::4].max():.4e}, "
      f"6 МПа {q[2::4].min():.4e}..{q[2::4].max():.4e}")

# test_rate_approaches_regime_from_opposite_sides
margins = []
for d in range(1, 31):
    mid, end = q[2 * d - 1], q[2 * d]
    ok = mid > end if d % 2 == 1 else mid < end
    assert ok, d
    margins.append(abs(mid - end) / end)
print(f"OK test_rate_approaches_regime_from_opposite_sides: мин. относит. разница {min(margins):.3e}")

# test_repressurization_leaves_undersaturated_oil
pvt = _create_pvt(cfg)
pb = float(pvt.pb(np.array([r["Rs0"]]))[0])
final = history.states[-1]
rs_eq = pvt.Rs_eq(final.p)
under = (final.regime == 2) & (final.p < pb)
gap = rs_eq[under] - final.Rs[under]
two = final.regime == 1
err2 = np.max(np.abs(final.Rs[two] - rs_eq[two]))
print(f"финал: pb = {pb/1e6:.4f} МПа; недонас. ячеек {np.count_nonzero(under)}, зазор "
      f"{gap.min():.3e}..{gap.max():.3f}; двухфазных {np.count_nonzero(two)}, "
      f"max|Rs-Rs_eq| {err2:.2e}; Sg==0 среди regime==1: "
      f"{np.count_nonzero(two & (final.Sg == 0.0))}")
assert np.count_nonzero(under) > 0
assert np.all(final.Rs[under] < rs_eq[under] - 1e-6)
assert err2 <= 1e-10
for n in range(2, 61, 4):
    st = history.states[n]
    assert not np.any((st.regime == 2) & (st.p < pb)), n
print("OK test_repressurization_leaves_undersaturated_oil")
