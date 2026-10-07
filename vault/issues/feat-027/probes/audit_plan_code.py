"""FEAT-027, аудит: код блоков «После:» шага 1 дословно — против ожиданий тестов плана.

Рабочий код не меняется: ветвь Била собрана подклассом StandingFullPVT
с методами из плана. Проверяются числа тестов 1, 3-10, 13, 15.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-027\\probes\\audit_plan_code.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(ROOT))

from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402
from gpn_multiphase_solver.units import PA_TO_PSI  # noqa: E402

MU_O_UNDERSATURATED_MODELS = ("none", "beal")


class PlanPVT(StandingFullPVT):
    """StandingFullPVT + код шага 1 плана."""

    def __init__(self, *args, mu_o_undersaturated: str = "none", **kw):
        if mu_o_undersaturated not in MU_O_UNDERSATURATED_MODELS:
            raise ValueError(
                f"mu_o_undersaturated = {mu_o_undersaturated!r} не поддерживается. "
                f"Доступные: {MU_O_UNDERSATURATED_MODELS}.")
        super().__init__(*args, **kw)
        self._mu_under = mu_o_undersaturated

    def _beal_slope(self, mu_ob):
        mu_ob_cP = np.asarray(mu_ob, float) * 1e3
        slope_cP_per_psi = 1e-3 * (0.024 * mu_ob_cP ** 1.6 + 0.038 * mu_ob_cP ** 0.56)
        return slope_cP_per_psi * 1e-3 * PA_TO_PSI

    def mu_o(self, p, Rs):
        p = np.asarray(p, float)
        Rs = np.asarray(Rs, float)
        mu_ob = self._mu_o_beggs(Rs)
        if self._mu_under == "none":
            return mu_ob
        dp_above = np.maximum(p - self.pb(Rs), 0.0)
        return mu_ob + self._beal_slope(mu_ob) * dp_above


def check(name, ok, detail=""):
    print(f"{'OK ' if ok else 'FAIL'} {name} {detail}")


FIX = dict(rho_o_std=800.0, rho_g_std=0.78, T0=300.0, Rs0=50.0,
           co_undersaturated=5e-10, c_p_oil=1880.0, c_p_gas=2800.0,
           mu_JT_oil_val=4e-7, mu_JT_gas_val=-4e-6, L_degas_val=168000.0)
none = PlanPVT(**FIX)
beal = PlanPVT(**FIX, mu_o_undersaturated="beal")
A = np.array

# 1: по умолчанию "none" при c_o > 0 — ровно Беггс–Робинсон
Rs = A([0.0, 10.0, 30.0, 50.0]); p = np.full(4, 20e6)
check("1 default none", np.array_equal(none.mu_o(p, Rs), none._mu_o_beggs(Rs)))

# 2: неизвестное значение
try:
    PlanPVT(**FIX, mu_o_undersaturated="vasquez_beggs"); check("2 raises", False)
except ValueError as e:
    check("2 raises", "mu_o_undersaturated" in str(e))

# 3: формула и отношения
for R, ref in ((10.0, 1.196301), (30.0, 1.151919), (50.0, 1.126037)):
    r = beal.mu_o(A([20e6]), A([R]))[0] / none.mu_o(A([20e6]), A([R]))[0]
    check(f"3 Rs={R:g}", abs(r / ref - 1) < 1e-6, f"{r:.6f} vs {ref}")

# 4: непрерывность при p_b
for R in (10.0, 30.0, 50.0, 300.0):
    pb = beal.pb(A([R]))
    eq = beal.mu_o(pb, A([R]))[0] == none.mu_o(pb, A([R]))[0]
    d = beal.mu_o(pb * (1 + 1e-9), A([R]))[0] / none.mu_o(pb, A([R]))[0] - 1
    check(f"4 Rs={R:g} pb={pb[0]/1e6:.4f}", eq and abs(d) < 1e-8, f"d={d:.2e}")

# 5: ниже p_b — без изменений
for R in (10.0, 30.0, 50.0):
    pb = beal.pb(A([R]))
    check(f"5 Rs={R:g}", beal.mu_o(0.5 * pb, A([R]))[0] == none.mu_o(0.5 * pb, A([R]))[0])

# 6: линейность и наклон
pb = beal.pb(A([30.0]))[0]
pp = pb + A([1, 2, 3, 4]) * 1e6
mu = beal.mu_o(pp, np.full(4, 30.0))
dmu = np.diff(mu)
check("6 linear", np.allclose(dmu, dmu[0], rtol=1e-9, atol=0),
      f"slope={dmu[0]/1e6:.6e} Па·с/Па vs 2.076451e-11")
check("6 slope", abs(dmu[0] / 1e6 / 2.076451e-11 - 1) < 1e-6)

# 7: p_b < 0
for pv, ref in ((2e6, 1.026356), (33e6, 1.401884)):
    r = beal.mu_o(A([pv]), A([0.0]))[0] / none.mu_o(A([pv]), A([0.0]))[0]
    check(f"7 p={pv/1e6:g}", np.isfinite(r) and abs(r / ref - 1) < 1e-6, f"{r:.6f}")

# 8: ограниченность около p_b = 0
Rsg = np.linspace(0, 2, 41)
r = beal.mu_o(np.full(41, 33e6), Rsg) / none.mu_o(np.full(41, 33e6), Rsg)
check("8 bounded", np.all(np.isfinite(r)) and r.max() <= 1.4019
      and np.all(np.diff(r) < 0) and np.abs(np.diff(r)).max() < 1e-3,
      f"max={r.max():.6f} jump={np.abs(np.diff(r)).max():.2e}")

# 9: пример 20 — Бил против Васкеса–Беггса
s20n = PlanPVT(800.0, 1.014, 380.0, 300.0, 3.3e-9)
s20 = PlanPVT(800.0, 1.014, 380.0, 300.0, 3.3e-9, mu_o_undersaturated="beal")
rb = s20.mu_o(A([33e6]), A([300.0]))[0] / s20n.mu_o(A([33e6]), A([300.0]))[0]
pp = 33e6 * PA_TO_PSI
m = 2.6 * pp ** 1.187 * np.exp(-11.513 - 8.98e-5 * pp)
rvb = (33e6 / s20.pb(A([300.0]))[0]) ** m
check("9 Beal~VB", abs(rb - rvb) < 1e-3 and abs(rb / 1.033892 - 1) < 1e-6,
      f"Бил {rb:.6f}, ВБ {rvb:.6f}")

# 10: B_o не меняется
pq = A([2e6, 20e6]); Rq = A([30.0, 30.0])
check("10 Bo", np.array_equal(beal.Bo(pq, Rq), none.Bo(pq, Rq)))

# 13: параметры baseline.json (850 / 0.85 / 350 К / 50), p = 20 МПа
bb = PlanPVT(850.0, 0.85, 350.0, 50.0, mu_o_undersaturated="beal")
bn = PlanPVT(850.0, 0.85, 350.0, 50.0)
r = bb.mu_o(A([20e6]), A([50.0]))[0] / bn.mu_o(A([20e6]), A([50.0]))[0]
check("13 baseline", abs(r / 1.095309 - 1) < 1e-6, f"{r:.6f}")

# 15: эталон Кирхгофа так, как его считает помощник шага 3
K, H, R_EXT, R_WELL, P_EXT, P_WF = 1e-13, 10.0, 50.0, 0.1, 20e6, 15e6
Rs = A([50.0])
Bo = bb.Bo(A([P_EXT]), Rs)[0]
mu_e = bb.mu_o(A([P_EXT]), Rs)[0]; mu_w = bb.mu_o(A([P_WF]), Rs)[0]
beta = (mu_e - mu_w) / (P_EXT - P_WF)
q = 2 * np.pi * K * H / (Bo * np.log(R_EXT / R_WELL)) * np.log(mu_e / mu_w) / beta
MOB_O = 903.8407518315244
Q_EXACT = 2.0 * np.pi * K * H * MOB_O * (P_EXT - P_WF) / np.log(R_EXT / R_WELL)
check("15 q", abs(q / 4.2597423435e-3 - 1) < 1e-9, f"{q:.10e}")
check("15 ratio", abs(q / Q_EXACT / 0.932299 - 1) < 1e-6, f"{q/Q_EXACT:.6f}")
