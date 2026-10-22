"""BUG-018: трассировка первого шага — почему Ньютон прототипа не сходится.

Конфиг — пример 20 из генератора FEAT-025 (R_s0 = 500, p_wf = 5 МПа) с
переопределениями из командной строки (как в make_configs.py: S_or, N, k ...).
Модель прототипа вызывается напрямую, одним шагом dt (без A-retry адаптера).
Методы модели подменяются в памяти только для журнала, физика не меняется.

Печатает по каждому вызову _newton_fixed_active_set (ступень advance, обход
active set): число активных ячеек, max S_g начального приближения, ячейки с
S_g > 1 - S_or; по итерациям — ||F||_inf, принятый alpha или причину отказа
линейного поиска: сколько пробных векторов отвергнуто _trial_is_reasonable
(и по какой границе: S_g > 0.98, S_g < нижней границы, R_s, p) и сколько —
из-за роста merit.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-018\\probes\\first_step_trace.py [dt_s] [ключ=значение ...]
    например: first_step_trace.py 86400 S_or=0.2 N=50 k=1e-13
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
FEAT025 = HERE.parents[1] / "feat-025" / "probes"
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", FEAT025):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import make_configs as mc  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

args = sys.argv[1:]
dt = float(args.pop(0)) if args and "=" not in args[0] else 86400.0
over = dict(a.split("=", 1) for a in args)
over.setdefault("log", "ERROR")

# ── Конфиг примера 20 с переопределениями ──
cfg_dict = mc.build("20", mc.SETS["20"], over)
d = HERE / "cfg"
d.mkdir(exist_ok=True)
import json  # noqa: E402
(d / "config.json").write_text(json.dumps(cfg_dict, indent=2, ensure_ascii=False), encoding="utf-8")
cfg = load_config(d / "config.json")
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
S_or = cfg.relperm.S_or
print(f"N = {cfg.grid.N}, S_or = {S_or}, k = {cfg.rock.permeability:.0e} м², "
      f"p_wf = {cfg.time.history[0].p_wf/1e6} МПа, dt = {dt:.0f} с")

# ── Журнал: обёртки над методами модели ──
stage = {"name": "исходный", "call": 0}
orig_newton = model._newton_fixed_active_set
orig_reasonable = model._trial_is_reasonable
orig_residual = model.residual
tally = {}


def reasonable(z, gas_active):
    ok = orig_reasonable(z, gas_active)
    if not ok:
        n = model.grid.n
        p, x = z[:n], z[n:]
        why = []
        if not np.all(np.isfinite(z)):
            why.append("NaN")
        if np.any(p <= 1.0):
            why.append("p<=1 бар")
        if np.any(x[gas_active] > 0.98):
            why.append("Sg>0.98")
        lo = model._sg_lower_bound
        if lo is not None and np.any(x[gas_active] < lo):
            why.append(f"Sg<{lo}")
        if np.any(x[~gas_active] < -1e-8) or np.any(x[~gas_active] > model.pvt.max_rs * 1.5):
            why.append("Rs")
        key = ",".join(why) or "?"
        tally[key] = tally.get(key, 0) + 1
    return ok


def newton(z0, state_old, dt_s, gas_active, **kw):
    stage["call"] += 1
    n = model.grid.n
    sg0 = np.asarray(z0)[n:][gas_active]
    over_lim = int(np.count_nonzero(sg0 > 1 - S_or))
    tally.clear()
    z, rep = orig_newton(z0, state_old, dt_s, gas_active, **kw)
    sg = z[n:][gas_active]
    print(f"   [{stage['name']}] вызов {stage['call']}: активных {int(gas_active.sum())}, "
          f"S_g нач. max {sg0.max() if sg0.size else 0:.3f}, ячеек с S_g > 1-S_or: {over_lim}; "
          f"итог: сошёлся={rep.converged}, итераций {rep.iterations}, ||F||_inf {rep.residual_inf:.3e}; "
          f"S_g кон. max {sg.max() if sg.size else 0:.3f}; отказов проверки пробных векторов: {dict(tally)}")
    return z, rep


model._newton_fixed_active_set = newton
model._trial_is_reasonable = reasonable

orig_fallback = model._fallback


def fallback(*a, **kw):
    stage["name"] = "3-я ступень" if model._line_search_l2 else "запасной путь"
    return orig_fallback(*a, **kw)


model._fallback = fallback

# ── Один шаг прототипа ──
st = init
model.set_bhp_control(cfg.time.history[0].p_wf / BAR_TO_PA)
proto = BlackOilState(pressure_bar=st.p / BAR_TO_PA, rs_sm3_sm3=st.Rs.copy(),
                      sg=st.Sg.copy(), gas_active=(st.regime == 1))
new, rep = model.advance(proto, dt)
print(f"итог шага: сошёлся = {rep.converged}; S_g[0] = {new.sg[0]:.4f}, "
      f"p[0] = {new.pressure_bar[0]*BAR_TO_PA/1e6:.3f} МПа")
