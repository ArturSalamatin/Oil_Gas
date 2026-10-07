"""FEAT-025: пример 20 (R_s0 = 500) — где сходится первый шаг.

Варианты (5 сут, суточный шаг после разгона):
  pwfX     — постоянное p_wf = X МПа с первого шага;
  rampA    — p_wf ступенями по 4 ч в первые сутки: 40, 30, 20, 12, 8, 5 МПа, дальше 5;
  closedSg — оценка S_g «закрытого сосуда» у забоя при мгновенном p_wf (печать).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\probe20.py [варианты]
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_configs as mc  # noqa: E402
import probe_run as pr  # noqa: E402

from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402

DAY = 86400.0
S = mc.SETS["20"]


def closed_vessel_sg(p_wf):
    """S_g, если R_s0 мгновенно выделяется до R_s(p_wf) в закрытом объёме."""
    pvt = StandingFullPVT(S["rho_o_std"], S["rho_g_std"], S["T0"], S["Rs0"])
    p = np.array([p_wf])
    rs = min(float(pvt.Rs_eq(p)[0]), S["Rs0"])
    vg = (S["Rs0"] - rs) * float(pvt.Bg(p)[0])
    vo = float(pvt.Bo(p, np.array([rs]))[0])
    return rs, vg / (vg + vo)


def write(name, hist, days=5, over=None):
    cfg = mc.build("20", S, {"days": str(days), **(over or {})})
    cfg["time"]["history"] = hist
    d = HERE / "p20" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return d / "config.json"


if __name__ == "__main__":
    print("S_g закрытого сосуда при мгновенном p_wf (1 - S_or = 0.8 — нефть неподвижна):")
    for pw in (5, 8, 12, 20, 30, 40):
        rs, sg = closed_vessel_sg(pw * 1e6)
        print(f"   p_wf = {pw:2d} МПа: R_s = {rs:6.1f}, S_g = {sg:.3f}")
    which = sys.argv[1:] or ["pwf20", "pwf12", "pwf8", "rampA"]
    for w in which:
        over = {}
        if w.startswith("sor"):
            # sorA_pwfB — S_or = A, постоянное p_wf = B МПа
            a, b = w[3:].split("_pwf")
            over = {"S_or": a}
            hist = [{"dt": DAY, "control": "pressure", "p_wf": float(b) * 1e6} for _ in range(5)]
            print(f"\n── 20 / {w}")
            pr.run_one(write(w, hist, over=over), every=1)
            continue
        if w.startswith("pwf"):
            pw = float(w[3:]) * 1e6
            hist = [{"dt": DAY, "control": "pressure", "p_wf": pw} for _ in range(5)]
        elif w == "rampA":
            steps = [40, 30, 20, 12, 8, 5]
            hist = [{"dt": 4 * 3600.0, "control": "pressure", "p_wf": x * 1e6} for x in steps]
            hist += [{"dt": DAY, "control": "pressure", "p_wf": 5e6} for _ in range(4)]
        else:
            continue
        print(f"\n── 20 / {w}")
        pr.run_one(write(w, hist), every=1)
