"""FEAT-022: почему гидродинамика не сходится на скачке p_wf вверх (13б).

Замер plan_numbers.py: 13б отказывает на первом скачке 6 -> 10.75 МПа
(t = 1 сут, p[0] = 6.13 МПа) даже при 512 подшагах (dt_sub = 7 с).

Здесь: состояние конца 1-х суток при 6 МПа (конфиг 12, два интервала по
0.5 сут), затем ОДИН вызов прототипа advance(state, dt) при разных целевых
p_wf и dt. Печатается отчёт Ньютона: сошёлся ли, итерации, невязка,
итерации набора активных ограничений, переключения фаз.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\upstep_diag.py
"""

import copy
import sys
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
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

BASE = SOLVER / "examples" / "12_large_drainage_radius" / "config.json"

cfg = load_config(BASE)
cfg.output.log_level = "ERROR"
iv = copy.deepcopy(cfg.time.history[0])
iv.dt, iv.p_wf = 43200.0, 6.0e6
cfg.time.history = [copy.deepcopy(iv), copy.deepcopy(iv)]
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
st = h.states[-1]
model = sim._hydro._model
print(f"состояние 1 сут: p[0] = {st.p[0]/1e6:.4f} МПа, p[1] = {st.p[1]/1e6:.4f}, "
      f"p[5] = {st.p[5]/1e6:.4f}, S_g[0] = {st.Sg[0]:.4f}, "
      f"двухфазных {int(np.count_nonzero(st.regime == 1))}")
print(f"r центров: {np.round(sim._grid.r_centers[:12], 3)}")
print(f"p (МПа):   {np.round(st.p[:12] / 1e6, 3)}")


def proto(s):
    return BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                         sg=s.Sg.copy(), gas_active=(s.regime == 1))


def attempt(target, dt):
    model.set_bhp_control(target / BAR_TO_PA)
    new, rep = model.advance(proto(st), dt)
    dp0 = (new.pressure_bar[0] * BAR_TO_PA - st.p[0]) / 1e3
    return (f"p_wf = {target/1e6:6.2f} МПа, dt = {dt:7.1f} с: converged = {rep.converged!s:5}, "
            f"it = {rep.iterations:3d}, res = {rep.residual_inf:.2e}, "
            f"aset = {rep.active_set_iterations}, switches = {rep.phase_switches}, "
            f"Δp[0] = {dp0:+9.1f} кПа, bhp_eff = {model._last_effective_bhp_bar/10:.3f} МПа")


for target in (6.0e6, 6.1e6, 6.2e6, 7.0e6, 8.0e6, 10.75e6):
    for dt in (3600.0, 60.0, 7.0, 1.0):
        print(attempt(target, dt))
    print()


# ── Гипотеза: Ньютон ломает переключатель «открыта / закрыта» внутри невязки ──
# blackoil.py:82-87: при p0 <= target дебит 0, иначе T_w·λ·(p0 - target).
# Невязка непрерывна, но негладка по p0 в точке p0 = target. Фиксируем ветку
# на всё время решения Ньютона (как набор активных фаз) и смотрим, сходится
# ли шаг 3600 с и согласована ли ветка с ответом.
import radial_blackoil.blackoil as bo_mod  # noqa: E402

orig = model._well_fluxes


def fixed_branch(branch):
    def wf(state):
        p0 = float(state.pressure_bar[0]); rs0 = float(state.rs_sm3_sm3[0])
        sg0 = float(state.sg[0])
        lo, lg = model._phase_mobilities_surface(p0, rs0, sg0)
        lo, lg = float(lo), float(lg)
        tw = model.grid.well_transmissibility_m3(model.skin)
        if branch == "shut":
            qow = qgfw = 0.0
            model._last_effective_bhp_bar = p0
        else:
            # «открыта» без ограничения знака: при p0 < target дебит отрицателен
            dpw = p0 - float(model.p_bhp_bar)
            qow = float(tw * lo * dpw * bo_mod.BAR_TO_PA)
            qgfw = float(tw * lg * dpw * bo_mod.BAR_TO_PA)
            model._last_effective_bhp_bar = float(model.p_bhp_bar)
        return qow, qgfw, float(rs0 * qow + qgfw)
    return wf


print("── фиксированная ветка скважины на всё время Ньютона ──")
for target in (6.2e6, 7.0e6, 10.75e6):
    for branch in ("shut", "open"):
        for dt in (3600.0, 60.0):
            model._well_fluxes = fixed_branch(branch)
            model.set_bhp_control(target / BAR_TO_PA)
            new, rep = model.advance(proto(st), dt)
            p0n = new.pressure_bar[0] * BAR_TO_PA
            q = model._well_fluxes(new)[0] if rep.converged else float("nan")
            # Согласованность: закрыта -> p0 <= target; открыта -> дебит >= 0
            ok = (p0n <= target) if branch == "shut" else (q >= 0.0)
            print(f"p_wf = {target/1e6:6.2f}, ветка {branch:4}, dt = {dt:6.0f} с: "
                  f"converged = {rep.converged!s:5}, it = {rep.iterations:2d}, "
                  f"aset = {rep.active_set_iterations}, switches = {rep.phase_switches}, "
                  f"p[0] = {p0n/1e6:.4f} МПа, q_o = {q:+.3e} м³ст/с, "
                  f"ветка согласована: {ok}")
model._well_fluxes = orig


# ── Почему не сходится ветка «закрыта»: что отбрасывает поиск по направлению ──
# blackoil.py:193-200: пробная точка принимается, если _trial_is_reasonable
# и |f|_inf убывает; иначе alpha /= 2, до 12 раз. Считаем причины отказа.
orig_reasonable = model._trial_is_reasonable
orig_residual = model.residual
log = Counter() if False else None
from collections import Counter  # noqa: E402

reasons = Counter()
last = {}


def reasonable(z, gas_active):
    n = model.grid.n
    p, x = z[:n], z[n:]
    if not np.all(np.isfinite(z)) or np.any(p <= 1.0):
        reasons["p <= 1 бар или не конечно"] += 1
        return False
    if np.any(x[~gas_active] < -1e-8) or np.any(x[~gas_active] > model.pvt.max_rs * 1.5):
        reasons["R_s однофазной ячейки вне границ"] += 1
        return False
    bad_lo = gas_active & (x < -0.05)
    bad_hi = gas_active & (x > 0.98)
    if np.any(bad_lo) or np.any(bad_hi):
        j = np.nonzero(bad_lo | bad_hi)[0]
        reasons[f"S_g двухфазной ячейки вне [-0.05, 0.98]: ячейки {j[:6].tolist()}"] += 1
        last["sg"] = (j[:6].tolist(), x[j[:6]].round(3).tolist(), (p[j[:6]] / 10).round(3).tolist())
        return False
    reasons["допустима"] += 1
    return True


model._trial_is_reasonable = reasonable
model._well_fluxes = fixed_branch("shut")
model.set_bhp_control(10.75e6 / BAR_TO_PA)
new, rep = model.advance(proto(st), 60.0)
print(f"\n── ветка shut, 10.75 МПа, dt = 60 с: converged = {rep.converged}, it = {rep.iterations}")
for k, v in reasons.most_common():
    print(f"   {v:4d} × {k}")
if "sg" in last:
    print(f"   последний отказ по S_g: ячейки {last['sg'][0]}, S_g = {last['sg'][1]}, "
          f"p = {last['sg'][2]} МПа")
print(f"   S_g до шага в ячейках 0-5: {st.Sg[:6].round(4).tolist()}")
model._trial_is_reasonable = orig_reasonable
model._well_fluxes = orig


# ── Эксперимент: ослабить нижнюю границу S_g двухфазной ячейки ──
# Не предложение правки, а проверка причины: если отказ — именно граница
# -0.05, то при нижней границе -1 Ньютон дойдёт до решения с S_g < 0, а
# внешний цикл набора активных ограничений (blackoil.py:209) переведёт
# ячейку в однофазный режим.
def relaxed(z, gas_active, lo=-1.0):
    n = model.grid.n
    p, x = z[:n], z[n:]
    if not np.all(np.isfinite(z)) or np.any(p <= 1.0):
        return False
    if np.any(x[~gas_active] < -1e-8) or np.any(x[~gas_active] > model.pvt.max_rs * 1.5):
        return False
    if np.any(x[gas_active] < lo) or np.any(x[gas_active] > 0.98):
        return False
    return True


model._trial_is_reasonable = relaxed
print("\n── нижняя граница S_g двухфазной ячейки -1 вместо -0.05, исходный переключатель ──")
for target in (7.0e6, 10.75e6):
    for dt in (3600.0, 60.0):
        print(attempt(target, dt))
model._trial_is_reasonable = orig_reasonable
