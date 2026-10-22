"""Проба DEBT-057: согласованность ṁ с выделением газа в гидродинамике на первых интервалах примера 18 — основа теста.

Запуск из numerical_solver/ (вывод — рядом, mdot_short.out.txt):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-057\\probes\\mdot_short.py

За каждый вызов solve: выделившийся газ по гидродинамике (запас a = φ(p)·S_o/B_o прототипа),
по ṁ энергии и остаток правила Лейбница по времени −Σ V·ΔR_s·Δa (DEBT-066). При φ энергии,
равной φ гидродинамики, «энергия − гидродинамика − остаток» — на уровне допуска Ньютона.
Варианты: base (φ0 в ṁ, как в коде) и B (φ(p^{n+1}) в ṁ — подмена на время расчёта).
"""
import dataclasses
import sys
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
OUT = Path(__file__).with_name("mdot_short.out.txt")
_lines = []


def log(*args):
    s = " ".join(str(a) for a in args)
    print(s)
    _lines.append(s)


import gpn_multiphase_solver as gms  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402

log("SOLVER =", SOLVER)
log("пакет  =", Path(gms.__file__).parent)
CFG = SOLVER / "examples" / "18_prototype_input" / "config.json"
ORIG_SOLVE = TridiagEnergySolver.solve
ORIG_DEG = TridiagEnergySolver.compute_degassing


def run(variant, n_intervals):
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    cfg.time.history = cfg.time.history[:n_intervals]
    p0 = cfg.initial_conditions.p0
    sim, init = SimulatorFactory.from_config(cfg)
    acc = dict(h=0.0, e=0.0, pred=0.0, calls=0)

    def phi_of(rock, p):
        return rock.porosity * np.exp(rock.compressibility * (p - p0))

    def deg_record(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext):
        out = ORIG_DEG(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext)
        self._last_mdot = -out / L
        return out

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        rock0 = self._rock
        st, sp = hydro_result.state, state_prev
        try:
            if variant == "B":
                # Подмена только для ṁ: в compute_degassing φ берётся из self._rock
                self._rock = dataclasses.replace(rock0, porosity=phi_of(rock0, st.p))
            T = ORIG_SOLVE(self, hydro_result, state_prev, dt, bc, collect)
        finally:
            self._rock = rock0
        V, pvt = self._grid.volumes, self._pvt
        a_new = phi_of(rock0, st.p) * (1 - st.Sg) / pvt.Bo(st.p, st.Rs)
        a_old = phi_of(rock0, sp.p) * (1 - sp.Sg) / pvt.Bo(sp.p, sp.Rs)
        G = hydro_result.G_o
        F0 = G[0] * st.Rs[0]
        FN = G[-1] * (bc.Rs_ext if G[-1] < 0 else st.Rs[-1])
        acc["h"] += -(np.sum(V * (a_new * st.Rs - a_old * sp.Rs)) + dt * (FN - F0))
        acc["e"] += np.sum(V * self._last_mdot) * dt / pvt.rho_g_std
        acc["pred"] += -np.sum(V * (st.Rs - sp.Rs) * (a_new - a_old))
        acc["calls"] += 1
        return T

    TridiagEnergySolver.solve = solve
    TridiagEnergySolver.compute_degassing = deg_record
    try:
        t0 = time.perf_counter()
        sim.run(init)
        el = time.perf_counter() - t0
    finally:
        TridiagEnergySolver.solve = ORIG_SOLVE
        TridiagEnergySolver.compute_degassing = ORIG_DEG
    gap = (acc["e"] - acc["h"] - acc["pred"]) / acc["h"]
    log(f"[{variant}, интервалов {n_intervals}] {el:.1f} с, вызовов {acc['calls']}: "
        f"гидродинамика {acc['h']:.6e}, ṁ {acc['e']:.6e}, остаток {acc['pred']:+.6e} м³ст; "
        f"(ṁ − гидр. − остаток)/гидр. = {gap:+.3e}; остаток/гидр. = {acc['pred'] / acc['h']:+.3e}")


if __name__ == "__main__":
    for n in (2, 5):
        for v in ("base", "B"):
            run(v, n)
    OUT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print(f"\nвывод: {OUT}")
