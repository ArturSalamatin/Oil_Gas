"""Проба DEBT-057: φ(p) в энергии на примере 18 — сдвиг T против погрешности шага и согласованность ṁ с гидродинамикой.

Запуск из numerical_solver/ (вывод — рядом, phi_energy.out.txt):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-057\\probes\\phi_energy.py

Варианты (код пакета не меняется — подмена методов TridiagEnergySolver на время расчёта):
    base    — как в коде: φ0 = rock.porosity во всех трёх местах;
    B       — φ(p^{n+1}) у флюида: φ·Σ S ρ c_p в (ρc_p)_eff, Q_ad, временная часть ṁ;
              скелет (1 − φ0)(ρc_p)_s и λ_eff — с φ0 (скелет сохраняет массу);
    A       — φ(p^{n+1}) везде, где стоит φ, включая (1 − φ) скелета и λ_eff;
    dt1800  — base с dt_integration = 1800 с: масштаб погрешности шага 3600 с;
    cr0     — base при c_r = 0 (гидродинамика другая): уровень несогласованности ṁ без φ.
"""
import dataclasses
import hashlib
import sys
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()  # запускать из numerical_solver/
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
OUT = Path(__file__).with_name("phi_energy.out.txt")
_lines = []


def log(*args):
    s = " ".join(str(a) for a in args)
    print(s)
    _lines.append(s)


import gpn_multiphase_solver as gms  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402

log("SOLVER =", SOLVER)
log("пакет  =", Path(gms.__file__).parent)

CFG = SOLVER / "examples" / "18_prototype_input" / "config.json"
DAY, BAR = 86400.0, 1e5

ORIG_SOLVE = TridiagEnergySolver.solve
ORIG_PROPS = TridiagEnergySolver.compute_cell_properties
ORIG_DEG = TridiagEnergySolver.compute_degassing


def phi_of(rock, p, p0):
    """φ(p) = φ0·exp(c_r·(p − p0)) — закон прототипа (rock.py), опорное давление p0 (factory.py)."""
    return rock.porosity * np.exp(rock.compressibility * (p - p0))


def run(variant, cfg_mut=None):
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    if cfg_mut is not None:
        cfg_mut(cfg)
    p0 = cfg.initial_conditions.p0
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    stats = dict(rel_h=0.0, rel_e=0.0, phi_dev=0.0, phi_max=0.0, calls=0)

    # Сетка: объёмы ячеек энергии и прототипа должны совпадать — иначе φ одна, а запасы разные
    vol_dev = np.max(np.abs(sim.grid.volumes / model.grid.bulk_volumes_m3 - 1.0))

    def props_B(self, p, Sg, Rs, So, T_old):
        # Свойства — с исходной породой (φ0): λ_eff и скелет остаются на φ0
        r = self._rock_orig
        saved, self._rock = self._rock, r
        try:
            props = ORIG_PROPS(self, p, Sg, Rs, So, T_old)
        finally:
            self._rock = saved
        props["rho_cp_eff"] = ((1 - r.porosity) * r.rho_cp_solid
                               + self._phi_p * (So * props["rho_o"] * props["c_p_o"]
                                                + Sg * props["rho_g"] * props["c_p_g"]))
        return props

    def deg_record(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext):
        out = ORIG_DEG(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext)
        self._last_mdot = -out / L          # Q_deg = −L·ṁ
        return out

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        rock0 = self._rock
        p_new = hydro_result.state.p
        phi_new = phi_of(rock0, p_new, p0)
        # φ энергии против φ прототипа (бар): та же формула?
        phi_proto = model.rock.porosity(p_new / BAR)
        stats["phi_dev"] = max(stats["phi_dev"], float(np.max(np.abs(phi_new / phi_proto - 1.0))))
        stats["phi_max"] = max(stats["phi_max"], float(np.max(np.abs(phi_new / rock0.porosity - 1.0))))
        self._phi_p = phi_new
        try:
            if variant in ("A", "B"):
                # A: φ(p) везде. B: φ(p) в Q_ad и ṁ через подменённую породу, скелет — в props_B
                self._rock = dataclasses.replace(rock0, porosity=phi_new)
                if variant == "B":
                    self._rock_orig = rock0
            T = ORIG_SOLVE(self, hydro_result, state_prev, dt, bc, collect)
        finally:
            self._rock = rock0

        # ── Согласованность ṁ с гидродинамикой (за вызов, м³ст газа) ──
        # Гидродинамика: выделившийся газ = −[Σ V·Δ(a·R_s) + dt·(F_N − F_0)],
        # a = φ(p)·S_o/B_o — запас нефтяного компонента на м³ пласта, F = G^o·R_s выше по потоку.
        st, sp = hydro_result.state, state_prev
        V = self._grid.volumes
        pvt = self._pvt
        a_new = phi_of(rock0, st.p, p0) * (1 - st.Sg) / pvt.Bo(st.p, st.Rs)
        a_old = phi_of(rock0, sp.p, p0) * (1 - sp.Sg) / pvt.Bo(sp.p, sp.Rs)
        G = hydro_result.G_o
        # Забой: при добыче (G < 0) выше по потоку ячейка 0; притока через забой в примере 18 нет
        F0 = G[0] * st.Rs[0]
        # Контур: приток (G < 0) несёт R_s притока, отток — R_s последней ячейки
        FN = G[-1] * (bc.Rs_ext if G[-1] < 0 else st.Rs[-1])
        rel_h = -(np.sum(V * (a_new * st.Rs - a_old * sp.Rs)) + dt * (FN - F0))
        rel_e = np.sum(V * self._last_mdot) * dt / pvt.rho_g_std
        # Гипотеза об остатке: ṁ берёт запас a^{n+1} при ΔR_s, а дискретное правило
        # Лейбница по времени Δ(aR) = a^{n+1}ΔR + R^n·Δa; адвективная часть вычитает
        # R^{n+1}·div G = −R^{n+1}·VΔa/dt. Разность энергия − гидродинамика = −Σ V·ΔR·Δa
        # (за вызов, м³ст), с φ энергии — у base φ0 в ṁ, поэтому только для B, A, cr0.
        stats["pred"] = stats.get("pred", 0.0) - np.sum(V * (st.Rs - sp.Rs) * (a_new - a_old))
        stats["rel_h"] += rel_h
        stats["rel_e"] += rel_e
        stats["calls"] += 1
        return T

    TridiagEnergySolver.solve = solve
    TridiagEnergySolver.compute_degassing = deg_record
    if variant == "B":
        TridiagEnergySolver.compute_cell_properties = props_B
    try:
        t0 = time.perf_counter()
        hist = sim.run(init)
        elapsed = time.perf_counter() - t0
    finally:
        TridiagEnergySolver.solve = ORIG_SOLVE
        TridiagEnergySolver.compute_degassing = ORIG_DEG
        TridiagEnergySolver.compute_cell_properties = ORIG_PROPS

    eb = compute_energy_balance(hist)
    T = np.array([s.T for s in hist.states])
    times = np.array(hist.times) / DAY
    log(f"\n[{variant}] расчёт {elapsed:.1f} с, вызовов solve {stats['calls']}, записей {len(times)}")
    log(f"  объёмы ячеек энергии / прототипа: max|отн. откл.| = {vol_dev:.2e}")
    log(f"  φ энергии / φ прототипа: max|отн. откл.| = {stats['phi_dev']:.2e}; "
        f"max|φ(p)/φ0 − 1| = {stats['phi_max']:.3e}")
    log(f"  баланс энергии: max rel_residual = {np.max(eb['rel_residual']):.2e}; "
        f"ΔE = {eb['delta_E'][-1]:.4e}, адиабата {eb['cum_adiab'][-1]:.4e}, "
        f"дегазация {eb['cum_deg'][-1]:.4e}, ДТ {eb['cum_jt'][-1]:.4e}, "
        f"конвекция {eb['cum_conv'][-1]:.4e}, теплопроводность {eb['cum_cond'][-1]:.4e} Дж")
    rh, re = stats["rel_h"], stats["rel_e"]
    log(f"  выделившийся газ за расчёт: гидродинамика {rh:.6e}, энергия (ṁ) {re:.6e} м³ст; "
        f"отн. расхождение {(re - rh) / rh:.3e}")
    log(f"  разность энергия − гидродинамика {re - rh:+.6e} м³ст; "
        f"предсказание −Σ V·ΔR_s·Δa = {stats['pred']:+.6e} м³ст")
    dT0 = T[1:, 0] - cfg.initial_conditions.T0
    log(f"  T(r_w) − T0: min {dT0.min():.5f} К (запись {np.argmin(dT0) + 1}), конец {dT0[-1]:.5f} К")
    # Отпечаток истории T — сверка с реализацией (t_fingerprint.py считает так же)
    log(f"  отпечаток T: {hashlib.sha256(np.ascontiguousarray(T).tobytes()).hexdigest()[:16]}")
    return dict(T=T, times=times)


if __name__ == "__main__":
    res = {}
    res["base"] = run("base")
    res["B"] = run("B")
    res["A"] = run("A")
    res["dt1800"] = run("dt1800", lambda c: setattr(c.time, "dt_integration", 1800.0))
    res["cr0"] = run("cr0", lambda c: setattr(c.rock, "compressibility", 0.0))

    base = res["base"]
    log("\n── Сдвиг T относительно base на записях истории (22 отметки SCHEDULE + начало) ──")
    for v in ("B", "A", "dt1800"):
        assert np.allclose(res[v]["times"], base["times"]), v
        d = res[v]["T"] - base["T"]
        log(f"  {v:7s}: max|ΔT(r_w)| = {np.max(np.abs(d[:, 0])):.3e} К, "
            f"max|ΔT| по полю = {np.max(np.abs(d)):.3e} К, "
            f"ΔT(r_w) в конце = {d[-1, 0]:+.3e} К")
    dAB = res["A"]["T"] - res["B"]["T"]
    log(f"  A − B  : max|ΔT| по полю = {np.max(np.abs(dAB)):.3e} К")
    log("\n── По записям: T(r_w) − T0, К ──")
    log("  запись  t, сут      base       B−base     A−base     dt1800−base")
    for i, t in enumerate(base["times"]):
        log(f"  {i:5d}  {t:9.5f}  {base['T'][i, 0] - 350.0:+.5f}  "
            f"{res['B']['T'][i, 0] - base['T'][i, 0]:+.2e}  "
            f"{res['A']['T'][i, 0] - base['T'][i, 0]:+.2e}  "
            f"{res['dt1800']['T'][i, 0] - base['T'][i, 0]:+.2e}")
    OUT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print(f"\nвывод: {OUT}")
