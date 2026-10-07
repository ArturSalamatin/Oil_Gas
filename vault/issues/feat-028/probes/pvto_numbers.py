"""Проба FEAT-028: эталонные числа для тестов рисунка PVT в стиле PVTO.

Правило выбора ветвей и границы экстраполяции — дословно те, что план
FEAT-028 (шаг 1) вносит в gpn_multiphase_solver/io/output.py. После
реализации проба должна печатать те же числа, что получает ядро.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\feat-028\\probes\\pvto_numbers.py
"""
import sys
from pathlib import Path

import numpy as np

# Консоль Windows по умолчанию cp1251 — без этого печать «──» падает.
sys.stdout.reconfigure(encoding="utf-8")

NS = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(NS / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(NS))

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import _create_pvt  # noqa: E402
from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402

# ── Правило шага 1 плана ──
_RS_STEPS = (1.0, 2.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0, 200.0, 250.0, 500.0)
_RS_ROWS_MAX = 7


def round_rs_rows(pvt, p):
    rs_lo = float(pvt.Rs_eq(p[:1])[0])
    rs_hi = float(pvt.Rs_eq(p[-1:])[0])
    for step in _RS_STEPS:
        rows = step * np.arange(np.ceil(rs_lo / step), np.floor(rs_hi / step) + 1)
        if rows.size <= _RS_ROWS_MAX:
            return rows
    return rows


def pvto_rows(pvt, p, Rs0, rs_tab):
    if rs_tab is not None:
        rows = np.asarray(rs_tab, float)
        rows = rows[pvt.pb(rows) <= p[-1]]
    else:
        rows = round_rs_rows(pvt, p)
    return rows[~np.isclose(rows, Rs0)]


def axis(p_range):
    return np.linspace(0.8 * p_range[0], 1.1 * p_range[1], 800)


def table_rs(pvt):
    return np.asarray(pvt._hydro._pvt.rs_values, float)


# ── 1. Тестовый PVT ядра (test_output.py): как в test_core_pvt_plot_standalone ──
pvt = StandingFullPVT(rho_o_std=850.0, rho_g_std=0.9, T0=350.0, Rs0=50.0)
p = axis((8e6, 20e6))
rows = pvto_rows(pvt, p, 50.0, None)
print("── StandingFullPVT(850, 0.9, 350, Rs0=50), p_range (8, 20) МПа ──")
print(f"  ось {p[0]/1e6:.2f}…{p[-1]/1e6:.2f} МПа, "
      f"Rs_eq на краях {float(pvt.Rs_eq(p[:1])[0]):.3f}…{float(pvt.Rs_eq(p[-1:])[0]):.3f}")
print(f"  ветви (без Rs0): {rows.tolist()}")
print(f"  p_b ветвей, МПа: {np.round(pvt.pb(rows)/1e6, 3).tolist()}; "
      f"p_b(Rs0) = {float(pvt.pb(np.array([50.0]))[0])/1e6:.3f}")
R = np.array([0.0, 1.0, 50.0, 150.0, 300.0])
print(f"  max|Rs_eq(pb(R)) - R| = {np.max(np.abs(pvt.Rs_eq(pvt.pb(R)) - R)):.2e}")
pvt0 = StandingFullPVT(rho_o_std=850.0, rho_g_std=0.9, T0=350.0, Rs0=0.0)
print(f"  Rs0 = 0: p_b(0) = {float(pvt0.pb(np.array([0.0]))[0])/1e6:.4f} МПа, "
      f"ветви: {pvto_rows(pvt0, p, 0.0, None).tolist()}")

# ── 2. Примеры: ветви на штатной оси (p_wf_min, p0) ──
print("\n── Примеры (p_range = (min p_wf, p0)) ──")
for name in ("01_single_phase_no_jt", "03_standing_corey", "05_standing_table_rp",
             "19_rs150_cooling", "20_rs300_cooling", "21_rs100_cooling",
             "04_table_table", "04a_high_gas_saturation", "11_degassing_at_boundary",
             "14_high_gor_cooling"):
    cfg = load_config(NS / "examples" / name / "config.json")
    pv = _create_pvt(cfg)
    Rs0 = float(cfg.initial_conditions.Rs0)
    pw = [h.p_wf for h in cfg.time.history if getattr(h, "p_wf", None) is not None]
    p = axis((min(pw), cfg.initial_conditions.p0))
    rs_tab = table_rs(pv) if cfg.pvt.model == "table" else None
    rows = pvto_rows(pv, p, Rs0, rs_tab)
    line = (f"  {name:26s} ось {p[0]/1e6:5.2f}…{p[-1]/1e6:5.2f} МПа; "
            f"Rs0={Rs0:g}; ветвей {rows.size}: {rows.tolist()}")
    if rs_tab is not None:
        pb_min, pb_max = (float(x) for x in pv.pb(rs_tab[[0, -1]]))
        left = p[0] < pb_min
        right = p[-1] > pb_max
        line += (f"; p_b(Rs_min..Rs_max) = {pb_min/1e6:.2f}…{pb_max/1e6:.2f} МПа; "
                 f"экстраполяция слева {left}, справа {right}")
    print(line)

# ── 3. Пример 14: узлы-начала строк 160 и 170 — на своих ветвях, не на Rs0 ──
cfg = load_config(NS / "examples" / "14_high_gor_cooling" / "config.json")
pv = _create_pvt(cfg)
print("\n── 14: начала строк против ветви Rs0 = 150 ──")
for r in (160.0, 170.0):
    pb = pv.pb(np.array([r]))
    print(f"  Rs = {r:g}: p_b = {float(pb[0])/1e6:.4f} МПа, "
          f"mu_o(p_b, {r:g}) = {float(pv.mu_o(pb, np.array([r]))[0]):.6e}, "
          f"mu_o(p_b, 150) = {float(pv.mu_o(pb, np.array([150.0]))[0]):.6e} Па·с")
p = axis((6e6, 24.5e6))
mus = [pv.mu_o(p, np.full_like(p, r)) for r in table_rs(pv)[:18]]
print(f"  веер mu_o на оси 4.8…26.95 МПа: {min(m.min() for m in mus):.3e}…"
      f"{max(m.max() for m in mus):.3e} Па·с")

# ── 4. Табличный PVT: Rs_eq(pb(R)) = R на строках ──
cfg = load_config(NS / "examples" / "04_table_table" / "config.json")
pv = _create_pvt(cfg)
R = table_rs(pv)
print(f"\n── 04: строки {R.tolist()}, p_b = {(pv.pb(R)/1e6).tolist()} МПа, "
      f"max|Rs_eq(pb(R)) - R| = {np.max(np.abs(pv.Rs_eq(pv.pb(R)) - R)):.2e}")
