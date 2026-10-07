"""DEBT-043, план: из чего состоит невязка баланса энергии — замер по подшагам.

Гипотеза (запись DEBT-043): невязка баланса — сумма по ячейкам невязки СЛАУ
температуры r = A·T^{n+1} − d, а её масштаб — ε·T·Σρc V на подшаг (запас
тепла пласта), а не ε·Σ|членов| (округление кумулятивных сумм, заметка
2026-09-24). Проверка: на каждом подшаге энергии

  res   — приращение невязки накопителя Δ(delta_E − Σ членов), Дж;
  slae  — dt·Σ_j (A·T^{n+1} − d)_j в ТОЧНОЙ арифметике (Fraction) по тем
          значениям double, что ушли в solve_banded, Дж. Это обратная
          ошибка прогонки: при точном решении СЛАУ она нулевая;
  asm   — res − slae: округления сборки a, b, c, d (cap·T_old, сумма
          коэффициентов в b) и самого накопителя;
  scale — ε·Σ_j ρc_j V_j T_j^{n+1}, Дж: масштаб шума по гипотезе.

Итог по примеру: N подшагов, финальная невязка (Дж и отн.), суммы slae и
asm, когерентная оценка Σ scale, оценка случайного блуждания √Σscale²,
z = |невязка| / √Σscale² и доля когерентности |Σ res| / √Σ res².

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\plan_slae_residual.py [пример ...]
    $env:DEBT043_SOLVER = "<дерево>\\numerical_solver"   # другое дерево, например worktree BUG-020
    $env:DEBT043_DT = "360"                              # шаг интегрирования вместо конфига
Без аргументов — все примеры ALL_EXAMPLES.
"""

import os
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path(os.environ.get("DEBT043_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

EPS = float(np.finfo(float).eps)   # 2.22e-16

ALL_EXAMPLES = [
    "01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey",
    "04_table_table", "04a_high_gas_saturation", "05_standing_table_rp",
    "06_table_corey_rp", "07_degassing_adiabatic_only", "08_degassing_jt",
    "09_degassing_latent_heat", "10_deep_degassing", "11_degassing_at_boundary",
    "12_large_drainage_radius", "13a_pwf_ramp_down", "13b_pwf_alternating",
    "14_high_gor_cooling", "15_oil_rate_ramp_up", "16_well_shut_in",
    "19_rs150_cooling", "20_rs300_cooling", "21_rs100_cooling",
]


def exact_row_sum(a, b, c, d, T):
    """Σ_j (a_j T_{j-1} + b_j T_j + c_j T_{j+1} − d_j) точно; a[0], c[N-1] в СЛАУ не входят."""
    N = len(T)
    s = Fraction(0)
    for j in range(N):
        s += Fraction(float(b[j])) * Fraction(float(T[j])) - Fraction(float(d[j]))
        if j > 0:
            s += Fraction(float(a[j])) * Fraction(float(T[j - 1]))
        if j < N - 1:
            s += Fraction(float(c[j])) * Fraction(float(T[j + 1]))
    return s


def residual_of(acc):
    return acc.delta_E - (acc.cum_adiab + acc.cum_conv + acc.cum_jt
                          + acc.cum_deg + acc.cum_cond)


def run(name):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    # Мелкий шаг, как в energy_balance_convergence.py (DT_LIST = 3600, 900, 360)
    if os.environ.get("DEBT043_DT"):
        cfg.time.dt_integration = float(os.environ["DEBT043_DT"])
    sim, init = SimulatorFactory.from_config(cfg)
    V = sim._grid.volumes

    held = {}
    rows = []   # (dt, res, slae, scale)

    # Матрица подшага: matrix_probe вызывается ДО решения (tridiag.py:152).
    def probe(a, b, c, d, dt, T_old, **_):
        held.update(a=a.copy(), b=b.copy(), c=c.copy(), d=d.copy(), dt=dt)

    sim._energy.matrix_probe = probe

    orig_acc = EnergyBalanceAccumulator.add_accumulation

    # Невязка на конце предыдущего подшага. Брать её в начале
    # add_accumulation нельзя: add_substep (до решения СЛАУ) уже добавил
    # источники этого подшага, и приращение потеряло бы их.
    prev = {"res": 0.0}

    def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
        orig_acc(self, T_new, T_prev, rho_cp_eff, dt)
        now = residual_of(self)
        res = now - prev["res"]
        prev["res"] = now
        slae = float(exact_row_sum(held["a"], held["b"], held["c"], held["d"], T_new)
                     * Fraction(held["dt"]))
        scale = EPS * float(np.sum(rho_cp_eff * V * T_new))
        rows.append((dt, res, slae, scale))

    EnergyBalanceAccumulator.add_accumulation = add_accumulation
    t0 = time.perf_counter()
    try:
        h = sim.run(init)
    finally:
        EnergyBalanceAccumulator.add_accumulation = orig_acc
    wall = time.perf_counter() - t0

    bal = compute_balance(h, sim._grid, cfg)
    R = np.array(rows)
    res, slae, scale = R[:, 1], R[:, 2], R[:, 3]
    asm = res - slae
    final_abs = float(bal["residual"][-1])
    final_rel = float(bal["rel_residual"][-1])
    norm = abs(final_abs) / final_rel if final_rel > 0 else float("nan")
    walk = float(np.sqrt(np.sum(scale ** 2)))
    coh = abs(float(np.sum(res))) / float(np.sqrt(np.sum(res ** 2)))
    # Детерминированная граница: |res за подшаг| ≤ c·scale подшага ⇒
    # |невязка| ≤ c·Σ scale при любой корреляции ошибок между подшагами.
    step_ratio = float(np.max(np.abs(res) / scale))
    # Кривая по подшагам: максимум отношения |накопленная невязка| / Σ scale
    # на всей траектории, а не только в конце.
    cum_ratio = float(np.max(np.abs(np.cumsum(res)) / np.cumsum(scale)))
    return dict(name=name, n=len(rows), N=sim._grid.N, wall=wall,
                final_abs=final_abs, final_rel=final_rel, norm=norm,
                sum_res=float(np.sum(res)), sum_slae=float(np.sum(slae)),
                sum_asm=float(np.sum(asm)),
                rms_slae=float(np.sqrt(np.mean(slae ** 2))),
                rms_asm=float(np.sqrt(np.mean(asm ** 2))),
                scale_mean=float(np.mean(scale)), coh_bound=float(np.sum(scale)),
                walk=walk, z=abs(final_abs) / walk,
                coh=coh, sqrt_n=float(np.sqrt(len(rows))),
                # отношение шума к нормировке: каким был бы rel при |невязка| = √Σscale²
                rel_walk=walk / norm,
                step_ratio=step_ratio, cum_ratio=cum_ratio,
                rel_coh=float(np.sum(scale)) / norm)


if __name__ == "__main__":
    names = sys.argv[1:] or ALL_EXAMPLES
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    out = []
    for nm in names:
        r = run(nm)
        out.append(r)
        print(f"\n=== {nm}: подшагов {r['n']}, N = {r['N']}, {r['wall']:.0f} с ===")
        print(f"  невязка финал {r['final_abs']:+.3e} Дж, отн. {r['final_rel']:.2e}, "
              f"нормировка Σ|членов| {r['norm']:.2e} Дж")
        print(f"  Σ res {r['sum_res']:+.3e} | Σ slae {r['sum_slae']:+.3e} | Σ asm {r['sum_asm']:+.3e} Дж")
        print(f"  ср.кв. за подшаг: slae {r['rms_slae']:.2e}, asm {r['rms_asm']:.2e}; "
              f"scale ср. {r['scale_mean']:.2e} Дж")
        print(f"  Σ scale (когерентно) {r['coh_bound']:.2e}, √Σscale² (блуждание) {r['walk']:.2e} Дж; "
              f"z = |невязка|/√Σscale² = {r['z']:.2f}")
        print(f"  когерентность |Σres|/√Σres² = {r['coh']:.2f} (случайно ~1, систематично ~√n = {r['sqrt_n']:.0f}); "
              f"√Σscale²/норм. = {r['rel_walk']:.2e}", flush=True)
        print(f"  max|res|/scale за подшаг {r['step_ratio']:.3f}; max по траектории |Σres|/Σscale "
              f"{r['cum_ratio']:.4f}; Σscale/норм. = {r['rel_coh']:.2e}", flush=True)

    print("\n пример                       | n    | отн. невязка | |невязка|, Дж | Σslae/Σres | √Σscale², Дж | z     "
          "| √Σscale²/норм. | Σscale/норм. | max|res|/scale | max|Σres|/Σscale")
    for r in out:
        share = r["sum_slae"] / r["sum_res"] if r["sum_res"] != 0 else float("nan")
        print(f" {r['name']:28s} | {r['n']:4d} | {r['final_rel']:.2e}     | {abs(r['final_abs']):.2e}      | "
              f"{share:+.2f}      | {r['walk']:.2e}     | {r['z']:5.2f} | {r['rel_walk']:.2e}       "
              f"| {r['rel_coh']:.2e}     | {r['step_ratio']:.3f}          | {r['cum_ratio']:.4f}")
