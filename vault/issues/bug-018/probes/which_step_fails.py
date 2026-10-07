"""BUG-018: на каком шаге истории падает расчёт и почему (пример 20 с переопределениями).

Полный sim.run конфига make_configs.build("20", ...). Обёртки журналируют:
номер интервала истории (вызов HydroSolver.solve), каждый вызов model.advance
(dt, сошёлся, ступень). При отказе — повтор advance на начальном состоянии
отказавшего интервала с наименьшим dt попыток, с журналом каждого вызова
_newton_fixed_active_set (ступень, активные ячейки, S_g, итог, причины отказа
пробных векторов) — та же логика, что first_step_trace.py.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-018\\probes\\which_step_fails.py [ключ=значение ...]
    например: which_step_fails.py k=1e-14
"""

import json
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

DAY = 86400.0
over = dict(a.split("=", 1) for a in sys.argv[1:])
EX = over.pop("ex", "20")   # пример генератора FEAT-025: 19, 20 или 21
over.setdefault("log", "ERROR")
d = HERE / "cfg_which"
d.mkdir(exist_ok=True)
(d / "config.json").write_text(json.dumps(mc.build(EX, mc.SETS[EX], over), indent=2,
                                          ensure_ascii=False), encoding="utf-8")
cfg = load_config(d / "config.json")
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
S_or = cfg.relperm.S_or

# ── Журнал интервалов и вызовов advance ──
interval = {"n": -1, "state": None}
calls = []          # (интервал, dt, сошёлся, fallback, globalized)
orig_advance = model.advance
orig_solve = sim._hydro.solve


def advance(state_old, dt_s, *a, **kw):
    new, rep = orig_advance(state_old, dt_s, *a, **kw)
    calls.append((interval["n"], dt_s, rep.converged, getattr(rep, "fallback", False),
                  getattr(rep, "globalized", False)))
    return new, rep


def solve(state, dt, bc):
    interval["n"] += 1
    interval["state"] = state
    return orig_solve(state, dt, bc)


model.advance = advance
sim._hydro.solve = solve
print(f"пример {EX}: N = {cfg.grid.N}, S_or = {S_or}, k = {cfg.rock.permeability:.0e} м², "
      f"p_wf = {cfg.time.history[0].p_wf/1e6} МПа")
try:
    sim.run(init)
    print(f"расчёт прошёл: вызовов advance {len(calls)}, отказов {sum(not c[2] for c in calls)}")
    sys.exit(0)
except RuntimeError as e:
    nf = interval["n"]
    print(f"ОТКАЗ на интервале истории № {nf} (с {nf} по {nf + 1} сут): {str(e)[:70]}…")

# Сводка по интервалам: сколько вызовов advance, были ли ступени 2–3
for n in range(nf + 1):
    cs = [c for c in calls if c[0] == n]
    ok = [c for c in cs if c[2]]
    print(f"   интервал {n}: вызовов {len(cs)}, принято {len(ok)}, "
          f"min dt принятого {min((c[1] for c in ok), default=float('nan')):.1f} с, "
          f"запасной путь {sum(c[3] and not c[4] for c in ok)}, 3-я ступень {sum(c[4] for c in ok)}")

# ── Повтор отказавшего шага с журналом Ньютона ──
st = interval["state"]
print(f"\nсостояние в начале интервала {nf}: S_g[0] = {st.Sg[0]:.4f}, p[0] = {st.p[0]/1e6:.3f} МПа, "
      f"двухфазных {int((st.regime == 1).sum())} из {st.p.size}, max S_g = {st.Sg.max():.4f}")
model.advance = orig_advance
stage = {"name": "исходный"}
tally = {}
orig_newton = model._newton_fixed_active_set
orig_reasonable = model._trial_is_reasonable
orig_fallback = model._fallback


def reasonable(z, gas_active):
    ok = orig_reasonable(z, gas_active)
    if not ok:
        n = model.grid.n
        p, x = z[:n], z[n:]
        why = []
        if np.any(x[gas_active] > 0.98):
            why.append("Sg>0.98")
        lo = model._sg_lower_bound
        if lo is not None and np.any(x[gas_active] < lo):
            why.append(f"Sg<{lo}")
        if np.any(x[~gas_active] < -1e-8) or np.any(x[~gas_active] > model.pvt.max_rs * 1.5):
            why.append("Rs")
        if np.any(p <= 1.0) or not np.all(np.isfinite(z)):
            why.append("p/NaN")
        tally[",".join(why) or "?"] = tally.get(",".join(why) or "?", 0) + 1
    return ok


def newton(z0, state_old, dt_s, gas_active, **kw):
    n = model.grid.n
    tally.clear()
    z, rep = orig_newton(z0, state_old, dt_s, gas_active, **kw)
    sg = z[n:][gas_active]
    sg0 = np.asarray(z0)[n:][gas_active]
    act = int(gas_active.sum())
    new_act = int((gas_active & ~state_old.gas_active).sum())
    print(f"   [{stage['name']}] активных {act} (новых {new_act}), S_g нач. max "
          f"{sg0.max() if sg0.size else 0:.3f}, сошёлся={rep.converged}, итераций {rep.iterations}, "
          f"||F||_inf {rep.residual_inf:.3e}, S_g кон. max {sg.max() if sg.size else 0:.3f}, "
          f"min {sg.min() if sg.size else 0:.3e}; отказы проверки: {dict(tally)}")
    return z, rep


def fallback(*a, **kw):
    stage["name"] = "3-я ступень" if model._line_search_l2 else "запасной путь"
    return orig_fallback(*a, **kw)


model._newton_fixed_active_set = newton
model._trial_is_reasonable = reasonable
model._fallback = fallback
for dt in (DAY, DAY / 512):
    stage["name"] = "исходный"
    print(f"\nповтор advance, dt = {dt:.1f} с:")
    proto = BlackOilState(pressure_bar=st.p / BAR_TO_PA, rs_sm3_sm3=st.Rs.copy(),
                          sg=st.Sg.copy(), gas_active=(st.regime == 1))
    new, rep = model.advance(proto, dt)
    print(f"   итог: сошёлся = {rep.converged}")
