"""BUG-019, решение 1: есть ли зона c_t < 0 в штатном примере 20 (k = 30 мД) и влияет ли она на результат.

Конфиг — numerical_solver/examples/20_rs500_cooling/config.json без изменений (кроме
уровня журнала). PVT та же, что в отказном варианте 10 мД: c_o,sat < 0 при p ≥ 345.5 бар.

A. Штатный расчёт 30 сут. По каждым суткам: двухфазные ячейки с c_t < 0 (сколько,
   где, S_g и p в них), монотонность профилей p(r) и S_g(r), дробление шага A-retry,
   ступени advance. В выбранные сутки — наибольшее вырожденное Δt (пучок A/Δt + B).
B. Сходимость по времени, первые 3 сут: dt_integration = 86400, 21600, 3600 с.
   Если зона c_t < 0 портит решение (некорректная задача), мельчение шага не сходится
   или отказывает; если безвредна — разности убывают примерно как Δt (первый порядок).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\example20_check.py
"""

import json
import time

import numpy as np

import common as c
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.units import BAR_TO_PA
from radial_blackoil.state import BlackOilState

SRC = c.SOLVER / "examples" / "20_rs500_cooling" / "config.json"
OUT = c.HERE / "ex20"
OUT.mkdir(exist_ok=True)
base = json.loads(SRC.read_text(encoding="utf-8"))
print(f"конфиг: {SRC.relative_to(c.SOLVER.parent)}; k = {base['rock']['permeability']:.0e} м², "
      f"R_s0 = {base['initial_conditions']['Rs0']}, N = {base['grid']['N']}, "
      f"{len(base['history'] if 'history' in base else base['time']['history'])} сут")


def build(days=None, dt_int=None, name="base"):
    d = json.loads(json.dumps(base))
    d["output"]["log_level"] = "ERROR"
    if days is not None:
        d["time"]["history"] = d["time"]["history"][:days]
    if dt_int is not None:
        d["time"]["dt_integration"] = float(dt_int)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return SimulatorFactory.from_config(load_config(path))


def extrema(v):
    """Число локальных экстремумов профиля (смен знака приращения, нулевые приращения пропущены)."""
    s = np.sign(np.diff(v))
    s = s[s != 0]
    return int(np.sum(s[1:] != s[:-1]))


# ═════════════ A. Штатный расчёт ═════════════
sim, init = build()
model = sim._hydro._model
pvt = model.pvt
n = model.grid.n
r_c = model.grid.centers_m
stages = []
orig_adv = model.advance


def advance(state_old, dt_s, *a, **kw):
    new, rep = orig_adv(state_old, dt_s, *a, **kw)
    stages.append((dt_s, rep.converged, bool(getattr(rep, "fallback", False)),
                   bool(getattr(rep, "globalized", False))))
    return new, rep


model.advance = advance
t0 = time.perf_counter()
hist = sim.run(init)
print(f"\n═══ A. Штатный расчёт: {time.perf_counter() - t0:.1f} с, вызовов advance {len(stages)}, "
      f"отказов {sum(not s[1] for s in stages)}, запасной путь {sum(s[1] and s[2] and not s[3] for s in stages)}, "
      f"3-я ступень {sum(s[3] for s in stages)}; дробление A-retry: "
      f"{sorted(set(h.n_substeps for h in hist.hydro_results))}")
print(f"  {'сут':>4} {'двухф.':>6} {'c_t<0':>6} {'i':>9} {'r, м':>13} {'S_g в зоне':>15} {'p в зоне, бар':>15} "
      f"{'min c_t':>9} {'экстр. p/S_g':>12} {'в зоне':>7} {'T_wf, К':>8}")
zone_days = {}
for k, (t, s) in enumerate(zip(hist.times, hist.states)):
    day = t / c.DAY
    if day < 0.5:
        continue
    mask = s.regime == 1
    pb = s.p / BAR_TO_PA
    ct = c.c_t_cells(pvt, pb, s.Sg, mask)
    z = np.where(mask & (ct < 0))[0]
    zone_days[round(day)] = z
    ex_p, ex_s = extrema(s.p), extrema(np.where(mask, s.Sg, 0.0))
    ez = (extrema(s.p[z]), extrema(s.Sg[z])) if z.size > 2 else (0, 0)
    twf = hist.well_data[k].T_wf if k < len(hist.well_data) else float("nan")
    if z.size:
        print(f"  {day:4.0f} {int(mask.sum()):6d} {z.size:6d} {z.min():4d}…{z.max():<4d} "
              f"{r_c[z.min()]:6.1f}…{r_c[z.max()]:<6.1f} {s.Sg[z].min():.4f}…{s.Sg[z].max():.4f} "
              f"{pb[z].min():7.1f}…{pb[z].max():<7.1f} {np.nanmin(ct):+9.2e} {ex_p:5d}/{ex_s:<6d} "
              f"{ez[0]:3d}/{ez[1]:<3d} {twf:8.3f}")
    else:
        print(f"  {day:4.0f} {int(mask.sum()):6d} {0:6d} {'—':>9} {'—':>13} {'—':>15} {'—':>15} "
              f"{np.nanmin(ct) if mask.any() else float('nan'):+9.2e} {ex_p:5d}/{ex_s:<6d} {'':>7} {twf:8.3f}")

print("\n  Наибольшее вырожденное Δt (J = A/Δt + B) против суточного шага:")
for day in (1, 2, 5, 10, 20, 30):
    k = int(np.argmin(np.abs(np.array(hist.times) - day * c.DAY)))
    s = hist.states[k]
    mask = s.regime == 1
    st = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(), gas_active=mask)
    sing = c.singular_dts(model, st, mask, model.pack(st, mask))
    print(f"    сут {day:2d}: вырожденных Δt {sing.size}; наибольшее {sing.max() if sing.size else float('nan'):.4g} с; "
          f"ближайшие к 86400: {', '.join(f'{x:.4g}' for x in sing[np.argsort(np.abs(np.log(sing / c.DAY)))[:2]]) if sing.size else '—'}")

# ═════════════ B. Сходимость по времени ═════════════
print("\n═══ B. Мельчение шага, 3 сут ═══")
DAYS = 3
runs = {}
for dt_int in (86400.0, 21600.0, 3600.0):
    simb, initb = build(days=DAYS, dt_int=dt_int, name=f"dt{int(dt_int)}")
    nsub = []
    t0 = time.perf_counter()
    try:
        hb = simb.run(initb)
        runs[dt_int] = hb
        nsub = sorted(set(h.n_substeps for h in hb.hydro_results))
        print(f"  dt_integration = {dt_int:7.0f} с: прошёл, {time.perf_counter() - t0:.1f} с, шагов {len(hb.hydro_results)}, "
              f"дробление A-retry {nsub}")
    except RuntimeError as e:
        print(f"  dt_integration = {dt_int:7.0f} с: ОТКАЗ — {str(e)[:160]}")

if 3600.0 in runs:
    ref = runs[3600.0].states[-1]
    zone = zone_days.get(DAYS, np.array([], int))
    print(f"  разность с dt = 3600 с на {DAYS} сут (вся сетка | зона c_t < 0 штатного расчёта, {zone.size} ячеек):")
    for dt_int in (86400.0, 21600.0):
        if dt_int not in runs:
            continue
        s = runs[dt_int].states[-1]
        dp, dsg, dT = np.abs(s.p - ref.p) / BAR_TO_PA, np.abs(s.Sg - ref.Sg), np.abs(s.T - ref.T)
        zp = f"{dp[zone].max():.3e}" if zone.size else "—"
        zs = f"{dsg[zone].max():.3e}" if zone.size else "—"
        print(f"    {dt_int:7.0f} с: max|Δp| {dp.max():.3e} | {zp} бар; max|ΔS_g| {dsg.max():.3e} | {zs}; "
              f"max|ΔT| {dT.max():.3e} К; ΔT_wf {abs(runs[dt_int].well_data[-1].T_wf - runs[3600.0].well_data[-1].T_wf):.3e} К")
