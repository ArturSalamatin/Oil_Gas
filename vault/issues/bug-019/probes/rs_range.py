"""BUG-019: при каких R_s0 нефть и газ примеров 19–21 остаются в области c_o,sat ≥ 0.

Предложение руководителя группы (2026-10-03): R_s0 ≤ 300 м³/м³.

1. Аналитика (StandingFullPVT решателя). Знак c_o,sat на кривой насыщения задаёт
   B_g − dB_o/dR_s; с ростом p он убывает, поэтому c_o,sat ≥ 0 на [p_wf, p_0] ⇔ p_0 ≤ p*,
   где B_g(p*) = dB_o/dR_s(R_s*), p* = p_b(R_s*). p_0 = p_b(R_s0) + 0.5 МПа, как в FEAT-025.
2. Расчёт решателем при R_s0 = 300: 30 сут — min c_t двухфазных ячеек, отказы шага;
   первые 3 сут при dt_integration = 86400, 21600, 3600 с — проходит ли мельчение шага
   (у примера 20 с R_s0 = 500 оно отказывает, example20_check.py).

Конфиги — замороженные конфиги FEAT-025 (feat-025/probes/final/, побайтно = примеры
на 2026-10-02): пример 20 с тех пор изменён и переименован в 20_rs300_cooling.
Тепловые параметры — из них без изменений: PVT изотермическая (T0), на гидродинамику
они не влияют.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\rs_range.py
"""

import json
import time

import numpy as np
from scipy.optimize import brentq

import common as c
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.units import BAR_TO_PA

EX = c.HERE.parents[1] / "feat-025" / "probes" / "final"
OUT = c.HERE / "rs_range"
OUT.mkdir(exist_ok=True)
MPA = 1e6
DP0 = 0.5 * MPA            # p_0 = p_b + 0.5 МПа, как в FEAT-025
P_INIT_19 = 37.0 * MPA     # начальное пластовое давление на 3.5–4 км (FEAT-025, «Условия»)
RS_LIST = (100.0, 150.0, 200.0, 250.0, 300.0)

# Нефть и газ примеров — базовые конфиги (19 и 21 различаются только R_s0)
FLUIDS = {
    "19/21": json.loads((EX / "19_rs150_cooling" / "config.json").read_text(encoding="utf-8")),
    "20": json.loads((EX / "20_rs500_cooling" / "config.json").read_text(encoding="utf-8")),
}


def lib_pvt(base, rs0):
    return StandingFullPVT(rho_o_std=base["pvt"]["rho_o_std"], rho_g_std=base["pvt"]["rho_g_std"],
                           T0=base["initial_conditions"]["T0"], Rs0=rs0)


def gap(pvt, rs, h=1e-3):
    """B_g(p_b(R_s)) − dB_o/dR_s: знак c_o,sat в насыщенном состоянии с газосодержанием R_s."""
    dbo = (pvt._Bo_standing(0.0, rs + h) - pvt._Bo_standing(0.0, rs - h)) / (2 * h)
    return float(pvt.Bg(pvt.pb(rs)) - dbo)


def c_o_sat(pvt, p, h=1e3):
    """(B_g·dR_s/dp − dB_o/dp)/B_o на кривой насыщения, 1/бар; p в Па."""
    rs = pvt.Rs_eq
    drs = (rs(p + h) - rs(p - h)) / (2 * h)
    dbo = (pvt._Bo_standing(p + h, rs(p + h)) - pvt._Bo_standing(p - h, rs(p - h))) / (2 * h)
    return float((pvt.Bg(p) * drs - dbo) / pvt._Bo_standing(p, rs(p)) * BAR_TO_PA)


def p0_of(pvt, rs0):
    """p_0 = p_b + 0.5 МПа с округлением до 0.1 МПа (как p0 в конфигах FEAT-025)."""
    return round((float(pvt.pb(rs0)) + DP0) / 1e5) * 1e5


# ═════════════ 1. Аналитика ═════════════
print("═══ 1. Аналитика: c_o,sat ≥ 0 на [p_wf, p_0] ⇔ p_0 ≤ p* ═══")
for name, base in FLUIDS.items():
    pvt = lib_pvt(base, 100.0)
    rs_star = brentq(lambda r: gap(pvt, r), 20.0, 3000.0)
    p_star = float(pvt.pb(rs_star))
    rs_max = float(pvt.Rs_eq(p_star - DP0))
    print(f"\nнефть {name}: ρ_o = {base['pvt']['rho_o_std']:.0f}, ρ_g = {base['pvt']['rho_g_std']}, "
          f"T0 = {base['initial_conditions']['T0']:.0f} К; R_s* = {rs_star:.1f} м³/м³, p* = {p_star / MPA:.2f} МПа; "
          f"при p_0 = p_b + 0.5 МПа: R_s0 ≤ {rs_max:.1f}")
    print(f"  {'R_s0':>5} {'p_b, МПа':>9} {'p_0, МПа':>9} {'c_o,sat(p_0)':>13} {'c_o,sat(p_0/2)':>15} "
          f"{'c_g(p_0)':>9}   1/бар")
    for rs0 in RS_LIST:
        p0 = p0_of(pvt, rs0)
        print(f"  {rs0:5.0f} {float(pvt.pb(rs0)) / MPA:9.2f} {p0 / MPA:9.1f} {c_o_sat(pvt, p0):+13.2e} "
              f"{c_o_sat(pvt, p0 / 2):+15.2e} {BAR_TO_PA / p0:9.2e}")
pvt19 = lib_pvt(FLUIDS["19/21"], 100.0)
print(f"\nнефть 19/21: p_b = {P_INIT_19 / MPA:.0f} МПа (начальное пластовое давление на 3.5–4 км) "
      f"при R_s0 = {float(pvt19.Rs_eq(P_INIT_19)):.1f}")


# ═════════════ 2. Расчёт решателем ═════════════
def build(base, rs0, k, days=None, dt_int=None, name="run"):
    d = json.loads(json.dumps(base))
    d["initial_conditions"]["Rs0"] = rs0
    d["initial_conditions"]["p0"] = p0_of(lib_pvt(base, rs0), rs0)
    d["rock"]["permeability"] = k
    d["output"]["log_level"] = "ERROR"
    if days is not None:
        d["time"]["history"] = d["time"]["history"][:days]
    if dt_int is not None:
        d["time"]["dt_integration"] = float(dt_int)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return SimulatorFactory.from_config(load_config(path))


# k = 1e-14 м² — «10 мД» проекта; для нефти 20 при R_s0 = 500 именно 10 мД отказывает (BUG-019)
CASES = (("19/21", 300.0, 1e-14), ("20", 300.0, 3e-14), ("20", 300.0, 1e-14))
for fluid, rs0, k in CASES:
    base = FLUIDS[fluid]
    tag = f"{fluid.replace('/', '_')}_rs{rs0:.0f}_k{k * 1e15:.0f}mD"
    p0 = p0_of(lib_pvt(base, rs0), rs0)
    p_wf = base["time"]["history"][0]["p_wf"]
    print(f"\n═══ 2. Нефть {fluid}, R_s0 = {rs0:.0f}, k = {k * 1e15:.0f} мД, p_0 = {p0 / MPA:.1f} МПа, "
          f"p_wf = {p_wf / MPA:.0f} МПа ═══")

    sim, init = build(base, rs0, k, name=tag)
    model = sim._hydro._model
    pvt = model.pvt
    stages = []

    def advance(state_old, dt_s, *a, _orig=model.advance, _log=stages, **kw):
        new, rep = _orig(state_old, dt_s, *a, **kw)
        _log.append(bool(rep.converged))
        return new, rep

    model.advance = advance
    t0 = time.perf_counter()
    try:
        hist = sim.run(init)
    except RuntimeError as e:
        print(f"  30 сут: ОТКАЗ — {str(e)[:200]}")
        continue
    ct_min, n_neg = np.inf, 0
    for s in hist.states:
        mask = s.regime == 1
        if mask.any():
            ct = c.c_t_cells(pvt, s.p / BAR_TO_PA, s.Sg, mask)
            ct_min = min(ct_min, float(np.nanmin(ct)))
            n_neg += int(np.sum(mask & (ct < 0)))
    s = hist.states[-1]
    mask = s.regime == 1
    print(f"  30 сут: прошёл, {time.perf_counter() - t0:.1f} с; вызовов advance {len(stages)}, "
          f"отказов {stages.count(False)}; дробление A-retry {sorted(set(h.n_substeps for h in hist.hydro_results))}")
    print(f"  min c_t двухфазных ячеек за 30 сут: {ct_min:+.2e} 1/бар; ячеек с c_t < 0 (сумма по суткам): {n_neg}")
    print(f"  на 30 сут: двухфазных {int(mask.sum())} из {mask.size}, max S_g = {s.Sg[mask].max():.3f}, "
          f"T_wf = {hist.well_data[-1].T_wf:.3f} К")

    runs = {}
    for dt_int in (86400.0, 21600.0, 3600.0):
        simb, initb = build(base, rs0, k, days=3, dt_int=dt_int, name=f"{tag}_dt{int(dt_int)}")
        t0 = time.perf_counter()
        try:
            runs[dt_int] = simb.run(initb)
            print(f"  3 сут, dt_integration = {dt_int:7.0f} с: прошёл, {time.perf_counter() - t0:.1f} с, "
                  f"дробление A-retry {sorted(set(h.n_substeps for h in runs[dt_int].hydro_results))}")
        except RuntimeError as e:
            print(f"  3 сут, dt_integration = {dt_int:7.0f} с: ОТКАЗ — {str(e)[:160]}")
    if 3600.0 in runs:
        ref = runs[3600.0]
        for dt_int in (86400.0, 21600.0):
            if dt_int in runs:
                sa, sr = runs[dt_int].states[-1], ref.states[-1]
                print(f"    {dt_int:7.0f} против 3600 с на 3 сут: max|Δp| {np.abs(sa.p - sr.p).max() / BAR_TO_PA:.3e} бар, "
                      f"max|ΔS_g| {np.abs(sa.Sg - sr.Sg).max():.3e}, "
                      f"ΔT_wf {abs(runs[dt_int].well_data[-1].T_wf - ref.well_data[-1].T_wf):.3e} К")
