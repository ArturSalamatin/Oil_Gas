"""BUG-022: числа текстов README 03 и 16, зависящие от допуска Ньютона, — база и эмуляция плана.

03: |GOR - Rs0| на забое по записям (README 03: «на 2-м шаге 6e-6, с 3-го — 2.5e-9»).
16: шаги останова после 21 сут — сколько итераций Ньютона, меняется ли состояние
    (README 16: «невязка состояния ниже абсолютного допуска, шаг принимается без итераций,
    давление больше не меняется ни в одном бите»), и изменение p за последние сутки до 21 сут.
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\texts_03_16.py <вариант>
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_mains  # noqa: E402  (ставит sys.path, cell_tol)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DAY = 86400.0
EX = run_mains.cell_tol.SOLVER / "examples"
variant = sys.argv[1]
run_mains.install_emulation(variant)
lines = [f"вариант {variant}"]

cfg = load_config(EX / "03_standing_corey" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
gor = np.array([w.q_g_std / w.q_o_std if w.q_o_std > 0 else np.nan for w in h.well_data])
dev = np.abs(gor - cfg.initial_conditions.Rs0)
lines.append("03 |GOR - Rs0| по записям 1..6: " + " ".join(f"{d:.2e}" for d in dev[1:7])
             + f"; max с записи 3: {np.nanmax(dev[3:]):.2e}; на конце {dev[-1]:.2e}")

cfg = load_config(EX / "16_well_shut_in" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
steps = []
adv = model.advance


def advance(state_old, dt_s, *a, **k):
    new, rep = adv(state_old, dt_s, *a, **k)
    steps.append((float(rep.iterations), bool(np.array_equal(new.pressure_bar, state_old.pressure_bar))))
    return new, rep


model.advance = advance
times = []
orig_solve = sim._hydro.solve


def solve(state, dt, bc):
    times.append(state.t)
    return orig_solve(state, dt, bc)


sim._hydro.solve = solve
h = sim.run(init)
after = [s for t, s in zip(times, steps) if t >= 21 * DAY - 1.0]
its = Counter(int(i) for i, _ in after)
same = sum(1 for _, eq in after if eq)
t = np.asarray(h.times) / DAY
k21 = int(np.argmin(np.abs(t - 21.0)))
k20 = int(np.argmin(np.abs(t - 20.0)))
dp_last = float(np.max(np.abs(h.states[k21].p - h.states[k20].p)))
lines.append(f"16 шаги с t >= 21 сут: {len(after)}, итераций Ньютона {dict(sorted(its.items()))}, "
             f"давление побитово не меняется на {same}; max|Δp| за сутки 20→21: {dp_last:.3g} Па; "
             f"R_s(r_w) на конце {h.states[-1].Rs[0]:.4f}")
text = "\n".join(lines)
print(text)
(HERE / f"texts_03_16_{variant}.out.txt").write_text(text + "\n", encoding="utf-8")
