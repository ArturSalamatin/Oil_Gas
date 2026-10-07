"""BUG-018: проверка причины — ограничить начальное S_g перед Ньютоном.

Обёртка над model._newton_fixed_active_set обрезает S_g двухфазных ячеек в
начальном приближении сверху значением cap. Больше cap бывает только
приближение «закрытого сосуда» у только что активированных ячеек: решённые
состояния имеют S_g < 0.5. Остальной алгоритм не меняется.

Если с cap < 1 - S_or отказ исчезает, причина — начальное приближение за
границей 1 - S_or. Печатает: сошёлся ли расчёт, сколько подшагов, T и S_g у
забоя на последней записи.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-018\\probes\\cap_initial_sg.py cap=0.75 ex=20 S_or=0.2 N=50 k=1e-13 days=5
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

over = dict(a.split("=", 1) for a in sys.argv[1:])
cap = float(over.pop("cap", "nan"))      # nan — без ограничения (контроль)
ex = over.pop("ex", "20")
pwf = over.pop("pwf", None)              # p_wf, МПа (по умолчанию — из набора примера)
save = over.pop("save", None)            # имя .npz для итоговых полей (сверка решений)
over.setdefault("log", "ERROR")
s = dict(mc.SETS[ex])
if pwf is not None:
    s["p_wf"] = float(pwf) * 1e6
d = HERE / "cfg_cap"
d.mkdir(exist_ok=True)
(d / "config.json").write_text(json.dumps(mc.build(ex, s, over), indent=2,
                                          ensure_ascii=False), encoding="utf-8")
cfg = load_config(d / "config.json")
sim, init = SimulatorFactory.from_config(cfg)
model = sim._hydro._model
n = model.grid.n
capped = [0]
orig_newton = model._newton_fixed_active_set


def newton(z0, state_old, dt_s, gas_active, **kw):
    if np.isfinite(cap):
        z0 = np.asarray(z0, float).copy()
        x = z0[n:]                       # вид на вторую половину вектора: S_g или R_s
        hit = gas_active & (x > cap)
        capped[0] += int(hit.sum())
        x[hit] = cap
    return orig_newton(z0, state_old, dt_s, gas_active, **kw)


model._newton_fixed_active_set = newton
calls = [0]
orig_advance = model.advance


def advance(*a, **kw):
    calls[0] += 1
    return orig_advance(*a, **kw)


model.advance = advance
print(f"пример {ex}: S_or = {cfg.relperm.S_or}, N = {cfg.grid.N}, k = {cfg.rock.permeability:.0e} м², "
      f"интервалов {len(cfg.time.history)}, cap = {cap}")
try:
    h = sim.run(init)
    st = h.states[-1]
    print(f"   СОШЁЛСЯ: вызовов advance {calls[0]} на {len(cfg.time.history)} интервалов, "
          f"обрезано начальных S_g: {capped[0]}; на {h.times[-1]/86400:.0f} сут "
          f"T(r_w) = {st.T[0]:.3f} К, S_g(r_w) = {st.Sg[0]:.4f}")
    if save:
        # Поля всех записей — для сверки решений, полученных из разных начальных приближений
        np.savez(HERE / f"{save}.npz",
                 p=np.array([x.p for x in h.states]), Sg=np.array([x.Sg for x in h.states]),
                 Rs=np.array([x.Rs for x in h.states]), T=np.array([x.T for x in h.states]),
                 q_o=np.array([w.q_o_std for w in h.well_data]),
                 q_g=np.array([w.q_g_std for w in h.well_data]))
except RuntimeError as e:
    print(f"   ОТКАЗ: {str(e)[:60]}…; вызовов advance {calls[0]}, обрезано {capped[0]}")
