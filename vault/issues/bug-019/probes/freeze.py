"""BUG-019, шаг 2.0: заморозить состояние на 1 сут и проверить воспроизведение отказа.

1. Конфиг генератора FEAT-025, пример 20, k = 1e-14 м², 2 сут → frozen/config.json.
2. sim.run до второго вызова гидродинамики; состояние, с которым адаптер начинает
   интервал 1, → frozen/state_t1.npz (p в Па, Rs, Sg, regime, T, t).
3. Ворота: исходный алгоритм из этого состояния при Δt = 168.75 с — 7 итераций,
   ||F||_inf = 2.896e-4, min S_g = 1.240e-3 (which_step_fails_k10.txt, BUG-018);
   при 337.5 с — сходится.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\freeze.py
"""

import json
import time

import numpy as np

import common as c
import make_configs as mc
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

c.FROZEN.mkdir(exist_ok=True)
cfg_dict = mc.build("20", mc.SETS["20"], {"k": "1e-14", "days": "2", "log": "ERROR"})
(c.FROZEN / "config.json").write_text(json.dumps(cfg_dict, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
cfg = load_config(c.FROZEN / "config.json")
sim, init = SimulatorFactory.from_config(cfg)


class _Stop(BaseException):
    """Остановить расчёт на входе в интервал 1 (A-retry на нём идёт минуты)."""


calls = {"n": 0}
orig_solve = sim._hydro.solve


def solve(state, dt, bc):
    if calls["n"] == 1:
        np.savez(c.FROZEN / "state_t1.npz", p=state.p, Rs=state.Rs, Sg=state.Sg,
                 regime=state.regime, T=state.T, t=state.t)
        raise _Stop
    calls["n"] += 1
    return orig_solve(state, dt, bc)


sim._hydro.solve = solve
t0 = time.perf_counter()
try:
    sim.run(init)
    raise SystemExit("расчёт не дошёл до интервала 1 — проверь конфиг")
except _Stop:
    pass
print(f"интервал 0 посчитан за {time.perf_counter() - t0:.1f} с; состояние на t = 1 сут сохранено")

# ── Ворота воспроизведения ──
model, _ = c.make_model()
st = c.load_state()
n = model.grid.n
print(f"N = {n}, двухфазных {int(st.gas_active.sum())}, S_g[0] = {st.sg[0]:.4f}, "
      f"p[0] = {st.pressure_bar[0] / 10:.4f} МПа, max S_g = {st.sg.max():.4f}")
z0 = model.pack(st, st.gas_active)
t0 = time.perf_counter()
for _ in range(20):
    model.residual(z0, st, c.DT_FAIL, st.gas_active)
print(f"одна невязка: {(time.perf_counter() - t0) / 20 * 1e3:.2f} мс")

for dt in (c.DT_FAIL, c.DT_OK):
    t0 = time.perf_counter()
    r = c.trace_newton(model, st, dt)
    rep, its = r["rep"], r["its"]
    sg = r["z_end"][n:][r["mask"]]
    print(f"\nΔt = {dt:.2f} с: {r['outcome']}, итераций {rep.iterations}, "
          f"||F||_inf {rep.residual_inf:.4e}, min S_g {sg.min():.4e}, допуск {r['tol']:.3e}, "
          f"{time.perf_counter() - t0:.1f} с")
    for k, it in enumerate(its):
        a = "—" if it["alpha"] is None else f"{it['alpha']:.6g} (откл. {it['fit']:.1e})"
        print(f"   k={k}: ||f||_inf {np.max(np.abs(it['f'])):.4e}, α {a}")
