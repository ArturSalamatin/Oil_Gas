"""Проба DEBT-066: остатки правила Лейбница по времени в уравнении энергии и сдвиг T от множителя ṁ со слоя n.

Запуск из numerical_solver/ (вывод — рядом, layer_residuals.out.txt):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-066\\probes\\layer_residuals.py

Для каждого примера — два расчёта:
  n+1 — как в коде: временная часть ṁ с запасом (φξ_o)^{n+1} (eq:mdot_disc);
  n   — вариант 1: множитель φ(p^n)·(1 − S_g^n)/B_o(p^n, R_s^n); подмена compute_degassing
        на время расчёта, остальное без изменений.

Проба 1 — сдвиг T (n минус n+1) на забое и максимум по сетке в моменты записи.
Проба 2 — в расчёте n+1 за каждый вызов solve, Дж, «схема минус согласованная с балансами масс»
в пересчёте на источник в правой части уравнения энергии:
  E_deg = +L·ρ_g^ст·Σ V·ΔR_s·Δ(φξ_o)       — множитель ṁ со слоя n+1 (DEBT-066);
  E_acc = −Σ V·Σ_α c_p,α·ΔM_α·ΔT            — накопление (ρc_p)_eff^{n+1}·ΔT вместо M^n·c_p·ΔT;
  E_ad  = +Σ V·Σ_α c_p,α·μ_JT,α·ΔM_α·Δp     — часть Q_ad с массами фаз слоя n+1.
M_α = φ(p)·S_α·ρ_α — масса фазы, кг на м³ пласта; c_p, μ_JT, L — при (p^{n+1}, T^n), как в схеме.
Согласованная форма — из Δ(M·h) − h^{n+1}·ΔM = M^n·Δh, dh = c_p·dT − c_p·μ_JT·dp (eq:dh_oil).
Масштаб — теплота дегазации D = Σ V·Q_deg·Δt расчёта n+1 (< 0 — охлаждение); для E_ad — ещё
cum_adiab (∫Q_ad из накопителя баланса). E_acc и E_ad разложены по фазам; у газа отдельно —
ячейки, где газ появился за шаг (M_g^n = 0: согласованная форма вклада не даёт).
Контроль подмены: выделение газа по ṁ против гидродинамики −[Σ V·Δ(φξ_o·R_s) + Δt·(F_N − F_0)], м³ст.
"""
import dataclasses
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
OUT = Path(__file__).with_name("layer_residuals.out.txt")
_lines = []


def log(*args):
    s = " ".join(str(a) for a in args)
    print(s, flush=True)
    _lines.append(s)


import gpn_multiphase_solver as gms  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402

log("SOLVER =", SOLVER)
log("пакет  =", Path(gms.__file__).parent)

ORIG_SOLVE = TridiagEnergySolver.solve
ORIG_DEG = TridiagEnergySolver.compute_degassing
DAY = 86400.0

# Пример → окна, сут (концы окон — моменты записи). Окна считаются от t = 0.
CASES = {
    "18_prototype_input": (1, 30),
    "14_high_gor_cooling": (1, 30),
    "20_rs300_cooling": (1, 30),
    # 15 сут — конец добычи, 16 сут — первые сутки останова
    "17_shut_in_strong_cooling": (1, 15, 16, 30),
}

# Поля записи за вызов solve. _o, _g — вклады фаз; E_ad_gnew — газ в ячейках,
# где он появился за шаг (S_g^n = 0, S_g^{n+1} > 0).
COLS = ("t", "E_deg", "A_deg", "E_acc", "A_acc", "E_ad", "A_ad",
        "E_acc_o", "E_acc_g", "E_ad_o", "E_ad_g", "E_ad_gnew",
        "D", "gas_h", "gas_m", "G0_max")


def make_config(name):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    if name.startswith("14_"):
        # Пример 14 — 360 сут с записью раз в 30 сут. Берём 30 сут посуточно:
        # шаг тот же (dt_integration = 1 сут), запись — каждые сутки.
        h0 = cfg.time.history[0]
        cfg.time.history = [dataclasses.replace(h0, dt=DAY) for _ in range(30)]
    return cfg


def run(name, variant):
    cfg = make_config(name)
    sim, init = SimulatorFactory.from_config(cfg)
    rec = []
    ctx = {"t": 0.0}

    def degassing(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext, p=None):
        if variant == "n":
            # Вариант 1: запас нефти старого слоя — все сомножители со слоя n.
            # В compute_degassing So, Bo, p входят только во временную часть.
            sp = ctx["sp"]
            So, Bo, p = 1.0 - sp.Sg, self._pvt.Bo(sp.p, sp.Rs), sp.p
        out = ORIG_DEG(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext, p=p)
        ctx["Q_deg"], ctx["L"] = out, L
        return out

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        st, sp = hydro_result.state, state_prev
        ctx["sp"] = sp
        T = ORIG_SOLVE(self, hydro_result, state_prev, dt, bc, collect)
        ctx["t"] += dt
        pvt, V = self._pvt, self._grid.volumes
        phi1, phi0 = self.porosity(st.p), self.porosity(sp.p)

        # ── Запас нефти φξ_o, м³ст/м³ пласта ──
        a1 = phi1 * (1 - st.Sg) / pvt.Bo(st.p, st.Rs)
        a0 = phi0 * (1 - sp.Sg) / pvt.Bo(sp.p, sp.Rs)
        L = ctx["L"]
        e_deg = L * pvt.rho_g_std * V * (st.Rs - sp.Rs) * (a1 - a0)

        # ── Массы фаз, кг/м³ пласта ──
        dMo = phi1 * (1 - st.Sg) * pvt.rho_o(st.p, st.Rs) - phi0 * (1 - sp.Sg) * pvt.rho_o(sp.p, sp.Rs)
        dMg = phi1 * st.Sg * pvt.rho_g(st.p) - phi0 * sp.Sg * pvt.rho_g(sp.p)
        cpo, cpg = pvt.c_p_oil(st.p, sp.T), pvt.c_p_gas(st.p, sp.T)
        jto, jtg = pvt.mu_JT_oil(st.p, sp.T), pvt.mu_JT_gas(st.p, sp.T)
        dT, dp = T - sp.T, st.p - sp.p
        e_acc_o, e_acc_g = -V * cpo * dMo * dT, -V * cpg * dMg * dT
        e_ad_o, e_ad_g = V * cpo * jto * dMo * dp, V * cpg * jtg * dMg * dp
        e_acc, e_ad = e_acc_o + e_acc_g, e_ad_o + e_ad_g
        gnew = (sp.Sg == 0.0) & (st.Sg > 0.0)

        # ── Теплота дегазации и выделение газа ──
        D = np.sum(V * ctx["Q_deg"]) * dt
        G = hydro_result.G_o
        # Знаки: G > 0 — от скважины. Забой при добыче G[0] ≤ 0, выше по потоку
        # ячейка 0; при G[0] > 0 состав со стороны скважины не определён —
        # G0_max в записи показывает, был ли такой случай.
        F0 = G[0] * st.Rs[0]
        FN = G[-1] * (bc.Rs_ext if G[-1] < 0 else st.Rs[-1])
        gas_h = -(np.sum(V * (a1 * st.Rs - a0 * sp.Rs)) + dt * (FN - F0))
        gas_m = np.sum(V * (-ctx["Q_deg"] / L)) * dt / pvt.rho_g_std
        rec.append((ctx["t"], e_deg.sum(), np.abs(e_deg).sum(), e_acc.sum(), np.abs(e_acc).sum(),
                    e_ad.sum(), np.abs(e_ad).sum(),
                    e_acc_o.sum(), e_acc_g.sum(), e_ad_o.sum(), e_ad_g.sum(), e_ad_g[gnew].sum(),
                    D, gas_h, gas_m, G[0]))
        return T

    TridiagEnergySolver.solve = solve
    TridiagEnergySolver.compute_degassing = degassing
    try:
        t0 = time.perf_counter()
        hist = sim.run(init)
        el = time.perf_counter() - t0
    finally:
        TridiagEnergySolver.solve = ORIG_SOLVE
        TridiagEnergySolver.compute_degassing = ORIG_DEG
    rec = np.array(rec)
    log(f"  [{variant}] {el:.1f} с, вызовов solve {len(rec)}, t_конец = {rec[-1, 0] / DAY:.6f} сут "
        f"(запись {hist.times[-1] / DAY:.6f}), max G_o[0] = {rec[:, -1].max():+.3e}")
    return hist, rec


def window_sums(rec, t_end):
    m = rec[:, 0] <= t_end * (1 + 1e-12)
    return dict(zip(COLS[1:-1], rec[m, 1:-1].sum(axis=0)))


def analyse(name, windows):
    log(f"\n=== {name} ===")
    hb, rb = run(name, "n+1")
    hv, rv = run(name, "n")
    tb = np.array(hb.times)
    assert np.allclose(tb, hv.times), "моменты записи расчётов различаются"
    T_init = hb.states[0].T
    for w in windows:
        t_end = w * DAY
        i_end = int(np.argmin(np.abs(tb - t_end)))
        assert abs(tb[i_end] - t_end) < 1e-6 * t_end, f"нет записи на {w} сут"
        sb, sv = window_sums(rb, t_end), window_sums(rv, t_end)
        D = sb["D"]
        # Масштабы из накопителя баланса энергии расчёта n+1 (DEBT-013): ∫Q_ad, ΔE
        bal = hb.balance[i_end]
        log(f"-- окно 0…{w} сут (D = {D:+.4e} Дж; накопитель: cum_deg = {bal['cum_deg']:+.4e}, "
            f"cum_adiab = {bal['cum_adiab']:+.4e}, delta_E = {bal['delta_E']:+.4e} Дж)")
        # Проба 2: остатки схемы n+1 в долях |D|, сумма со знаком и сумма модулей по ячейкам и шагам
        for k in ("deg", "acc", "ad"):
            log(f"   E_{k:<3} = {sb['E_' + k]:+.4e} Дж ({sb['E_' + k] / abs(D):+.3e} |D|), "
                f"Σ|·| = {sb['A_' + k]:.4e} Дж ({sb['A_' + k] / abs(D):.3e} |D|)")
        log(f"   по фазам, Дж: E_acc нефть {sb['E_acc_o']:+.3e}, газ {sb['E_acc_g']:+.3e}; "
            f"E_ad нефть {sb['E_ad_o']:+.3e}, газ {sb['E_ad_g']:+.3e} "
            f"(из них ячейки, где газ появился за шаг, {sb['E_ad_gnew']:+.3e}); "
            f"E_ad / cum_adiab = {sb['E_ad'] / bal['cum_adiab']:+.3e}")
        # Контроль: в n+1 ṁ − гидр. ≈ −Σ V ΔR_s Δ(φξ_o); в n — на уровне допуска Ньютона
        for tag, s in (("n+1", sb), ("n", sv)):
            log(f"   газ [{tag}]: гидродинамика {s['gas_h']:.6e} м³ст, ṁ {s['gas_m']:.6e}, "
                f"(ṁ − гидр.)/гидр. = {(s['gas_m'] - s['gas_h']) / s['gas_h']:+.3e}")
        # Проба 1: сдвиг T
        dT = np.array([hv.states[i].T - hb.states[i].T for i in range(i_end + 1)])
        cool = T_init[0] - hb.states[i_end].T[0]
        # Относительный сдвиг забоя по всем записям окна: |ΔT_w| к изменению T_w
        # от начального в тот же момент (запись t = 0 исключена — там оба нуля)
        cool_all = np.array([T_init[0] - hb.states[i].T[0] for i in range(1, i_end + 1)])
        rel = np.abs(dT[1:, 0]) / np.abs(cool_all)
        k = int(np.argmax(rel))
        log(f"   T: max |сдвиг забоя| / |изменение T забоя| по записям 0…{w} сут = {rel[k]:.3e} "
            f"при t = {tb[k + 1] / 3600:.4g} ч (сдвиг {dT[k + 1, 0]:+.3e} K, изменение {cool_all[k]:+.4e} K)")
        log(f"   T: охлаждение забоя (n+1) {cool:+.4e} K; сдвиг n − (n+1) на {w} сут: забой "
            f"{dT[-1, 0]:+.3e} K, max|·| по сетке {np.abs(dT[-1]).max():.3e} K; "
            f"max по записям 0…{w} сут: забой {np.abs(dT[:, 0]).max():.3e} K, "
            f"сетка {np.abs(dT).max():.3e} K")


if __name__ == "__main__":
    for name, windows in CASES.items():
        analyse(name, windows)
    OUT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print(f"\nвывод: {OUT}")
