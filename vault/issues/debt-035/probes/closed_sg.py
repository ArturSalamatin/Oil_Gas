"""DEBT-035: S_g «закрытого сосуда» у забоя примеров 19 и 21 и порог S_or, выше которого её ограничивает узел ОФП.

S_g = d·B_g/(B_o + d·B_g), d = R_s0 − R_s(p_wf) — как в абзаце «Сходимость» README.
Порог: S_g > 1 − S_or ⇔ S_or > 1 − S_g (при S_or выше порога стартовую S_g ограничивает
наибольший узел таблицы ОФП с k_ro > 0 — BUG-018).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-035\\probes\\closed_sg.py
"""

from pathlib import Path

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.pvt.standing import StandingFullPVT

EXAMPLES = Path(__file__).resolve().parents[4] / "numerical_solver" / "examples"

for name in ("19_rs150_cooling", "21_rs100_cooling"):
    cfg = load_config(EXAMPLES / name / "config.json")
    ic, pv = cfg.initial_conditions, cfg.pvt
    pvt = StandingFullPVT(pv.rho_o_std, pv.rho_g_std, ic.T0, ic.Rs0)
    p_wf = cfg.time.history[0].p_wf
    p = np.array([p_wf])
    rs = min(float(pvt.Rs_eq(p)[0]), ic.Rs0)
    d = ic.Rs0 - rs                       # выделившийся газ, м³ст/м³ст нефти
    vg = d * float(pvt.Bg(p)[0])          # объём газа при p_wf на 1 м³ст нефти
    vo = float(pvt.Bo(p, np.array([rs]))[0])
    sg = vg / (vg + vo)
    print(f"{name}: p_wf = {p_wf / 1e6:.1f} МПа, R_s(p_wf) = {rs:.2f}, d = {d:.2f}, "
          f"S_g закр = {sg:.4f}, S_or_порог = 1 - S_g = {1 - sg:.4f}, "
          f"S_or в конфиге = {cfg.relperm.S_or}")
