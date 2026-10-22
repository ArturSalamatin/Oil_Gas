"""FEAT-027, проба: VAL-001 с вязкостью Била выше p_b против решения Кирхгофа.

Зачем: обосновать допуск интеграционного теста в плане до реализации.
mu_o подменяется на уровне класса (кода ветви ещё нет); всё остальное —
штатный путь load_config → SimulatorFactory → run.

Эталон. Однофазный стационарный приток, c_o = 0 (B_o = const), k_ro = 1,
p > p_b всюду. Подстановка Кирхгофа m(p) = ∫ dp/mu(p) сводит задачу к Дюпюи:
    q_std = 2 pi k h / (B_o ln(R_ext/r_w)) · ∫_{p_wf}^{p_ext} dp / mu(p),
при mu = mu_ob + beta (p - p_b):  ∫ = ln(mu(p_ext)/mu(p_wf)) / beta.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-027\\probes\\val001_beal.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(ROOT))

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402
from gpn_multiphase_solver.units import PA_TO_PSI  # noqa: E402

CFG = ROOT / "configs" / "val001.json"


def _beal_coef_cP_per_psi(mu_ob_cP):
    """d mu_o / dp выше p_b по Билу–Стендингу, сП/psi."""
    return 1e-3 * (0.024 * mu_ob_cP ** 1.6 + 0.038 * mu_ob_cP ** 0.56)


def mu_o_beal(self, p, Rs):
    """mu_o = mu_ob + 0.001 (p - p_b)(0.024 mu_ob^1.6 + 0.038 mu_ob^0.56), сП и psi."""
    p = np.asarray(p, float)
    Rs = np.asarray(Rs, float)
    mu_ob_cP = self._mu_o_beggs(Rs) * 1e3
    # Ниже p_b при фиксированном Rs — прежняя насыщенная ветвь (прибавка 0).
    dp_psi = np.maximum(p - self.pb(Rs), 0.0) * PA_TO_PSI
    return (mu_ob_cP + dp_psi * _beal_coef_cP_per_psi(mu_ob_cP)) * 1e-3


def run(N, beal):
    orig = StandingFullPVT.mu_o
    if beal:
        StandingFullPVT.mu_o = mu_o_beal
    try:
        cfg = load_config(CFG)
        cfg.grid.N = N
        sim, init = SimulatorFactory.from_config(cfg)
        hist = sim.run(init)
        return cfg, sim, hist
    finally:
        StandingFullPVT.mu_o = orig


def q_exact(cfg, beal):
    g, rk, ic = cfg.geometry, cfg.rock, cfg.initial_conditions
    p_ext = ic.p0
    p_wf = cfg.time.history[0].p_wf
    pvt = StandingFullPVT(cfg.pvt.rho_o_std, cfg.pvt.rho_g_std, ic.T0, ic.Rs0, 0.0)
    Rs = np.array([ic.Rs0])
    Bo = pvt.Bo(np.array([p_ext]), Rs)[0]
    mu_ob = pvt._mu_o_beggs(Rs)[0]
    pb = pvt.pb(Rs)[0]
    C = 2 * np.pi * rk.permeability * g.h / (Bo * np.log(g.R_ext / g.r_well))
    if not beal:
        return C * (p_ext - p_wf) / mu_ob, dict(pb=pb, mu_ob=mu_ob)
    beta = _beal_coef_cP_per_psi(mu_ob * 1e3) * 1e-3 * PA_TO_PSI   # Па·с / Па
    mu_e = mu_ob + beta * (p_ext - pb)
    mu_w = mu_ob + beta * (p_wf - pb)
    return C * np.log(mu_e / mu_w) / beta, dict(pb=pb, mu_ob=mu_ob, beta=beta,
                                                  mu_e=mu_e, mu_w=mu_w)


if __name__ == "__main__":
    cfg0 = load_config(CFG)
    q0, info0 = q_exact(cfg0, beal=False)
    q1, info1 = q_exact(cfg0, beal=True)
    print(f"p_b(Rs0) = {info1['pb']/1e6:.4f} МПа, mu_ob = {info1['mu_ob']*1e3:.6f} сП")
    print(f"beta = {info1['beta']:.6e} Па·с/Па = {info1['beta']/info1['mu_ob']:.6e} 1/Па (относит.)")
    print(f"mu(p_wf)/mu_ob = {info1['mu_w']/info1['mu_ob']:.6f}, "
          f"mu(p_ext)/mu_ob = {info1['mu_e']/info1['mu_ob']:.6f}")
    print(f"q_exact: без Била {q0:.10e}, с Билом {q1:.10e}, отношение {q1/q0:.6f}")
    print("  N    q_FVM(none)/q_ex - 1    q_FVM(beal)/q_ex - 1")
    prev = None
    for N in (20, 40, 80, 160):
        _, _, h0 = run(N, beal=False)
        cfg, _, h1 = run(N, beal=True)
        e0 = h0.well_data[-1].q_o_std / q0 - 1
        e1 = h1.well_data[-1].q_o_std / q1 - 1
        order = "" if prev is None else f"   порядок {np.log2(abs(prev/e1)):.2f}"
        print(f"{N:4d}   {e0:+.3e}             {e1:+.3e}{order}")
        prev = e1
