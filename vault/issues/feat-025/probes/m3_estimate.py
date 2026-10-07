"""FEAT-025: изоэнтальпийная оценка ΔT_w (модель М.3) на константах конфигов.

На 1 м³ст нефти, состав потока GOR = R_s0, теплопроводность не учтена:
    C dT = (m_o c_p,o mu_JT,o + m_g c_p,g mu_JT,g) dp - L dm_g,
    m_o = rho_o,st + R_s rho_g,st,  m_g = (R_s0 - R_s) rho_g,st,  C = m_o c_p,o + m_g c_p,g.
R_s(p) = min(R_s^eq(p), R_s0) — StandingFullPVT решателя при T0. Путь p0 → p_wf.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\m3_estimate.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
sys.path.insert(0, str(SOLVER))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402

NAMES = ["19_rs150_cooling", "20_rs500_cooling", "21_rs100_cooling"]


def m3(cfg):
    ic, pc, tc = cfg.initial_conditions, cfg.pvt, cfg.thermal
    pvt = StandingFullPVT(pc.rho_o_std, pc.rho_g_std, ic.T0, ic.Rs0)
    p0, pw = ic.p0, cfg.time.history[-1].p_wf
    rg, ro, Rs0 = pc.rho_g_std, pc.rho_o_std, ic.Rs0
    ps = np.linspace(p0, pw, 4001)
    rs = np.minimum(pvt.Rs_eq(ps), Rs0)
    a = b = c = 0.0
    for i in range(len(ps) - 1):
        dp = ps[i + 1] - ps[i]
        r = 0.5 * (rs[i] + rs[i + 1])
        mo, mg = ro + r * rg, (Rs0 - r) * rg
        C = mo * tc.c_p_oil + mg * tc.c_p_gas
        a += mo * tc.c_p_oil * tc.mu_JT_oil * dp / C
        b += mg * tc.c_p_gas * tc.mu_JT_gas * dp / C
        c += -tc.L_degas * (rs[i] - rs[i + 1]) * rg / C
    xg = (Rs0 - rs[-1]) * rg / (ro + Rs0 * rg)
    pb = float(pvt.pb(np.array([Rs0]))[0])
    return pb, a, b, c, xg, rs[-1]


if __name__ == "__main__":
    for nm in NAMES:
        cfg = load_config(HERE / "final" / nm / "config.json")
        pb, a, b, c, xg, rsw = m3(cfg)
        print(f"{nm}: p_b = {pb/1e6:.3f} МПа, p0 = {cfg.initial_conditions.p0/1e6} → "
              f"p_wf = {cfg.time.history[-1].p_wf/1e6} МПа: ΔT_w = {a+b+c:+.2f} К "
              f"(нефть {a:+.2f}, газ {b:+.2f}, L {c:+.2f}); R_s(p_wf) = {rsw:.1f}, "
              f"доля газа в потоке у забоя x_g = {xg:.3f}")
