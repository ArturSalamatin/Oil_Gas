"""FEAT-032 (планирование): числа тестов примеров 16 и 17 — штатно и с нарастанием h0.

Числа — те, что проверяют TestWellShutIn и TestShutInStrongCooling
(tests/test_examples.py), и члены баланса энергии из их докстрингов и README.
Нарастание — эмуляция варианта 2 (ramp_probe.patch), первый интервал сменой
не считается (решение пользователя). Отпечаток истории — для сверки
реализации с эмуляцией: код FEAT-032 обязан дать тот же отпечаток.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P <h0, с>
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ramp_probe import SOLVER_ROOT, fingerprint, patch  # noqa: E402

sys.path.insert(0, str(SOLVER_ROOT / "examples"))
import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

# DEBT-011 переносит баланс энергии в ядро и делает create_pvt публичной без
# псевдонима: проба работает и до, и после его влития.
try:
    from gpn_multiphase_solver.factory import create_pvt as _create_pvt  # noqa: E402
except ImportError:
    from gpn_multiphase_solver.factory import _create_pvt  # noqa: E402
try:
    from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402

    def compute_balance(history, grid, config):
        return compute_energy_balance(history)
except ImportError:
    from energy_balance import compute_balance  # noqa: E402

E = 15   # запись конца добычи (15 сут) в обоих примерах


def run(name, h0):
    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    stats = patch(sim, h0, include_first=False) if h0 is not None else None
    hist = sim.run(s0)
    return cfg, sim._grid, hist, stats


def numbers(name, cfg, grid, hist):
    """Словарь чисел, которые проверяют тесты примера."""
    st = hist.states
    pvt = _create_pvt(cfg)
    Rs0 = cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    pw = np.array([s.p[0] for s in st])
    T = np.array([s.T[0] for s in st])
    rs = np.array([s.Rs[0] for s in st])
    final = st[-1]
    rs_eq = pvt.Rs_eq(final.p)
    above = [n for n in range(E, len(pw)) if pw[n] > pb]
    n_gas = [int(np.count_nonzero(s.Sg > 0.0)) for s in st]
    bal = compute_balance(hist, grid, cfg)
    out = {
        "отпечаток": fingerprint(hist),
        "q_o[E]": float(hist.well_data[E].q_o_std),
        "T[E]": T[E],
        "p_w[E+1], МПа": pw[E + 1] / 1e6,
        "p_w монотонна после E": bool(np.all(np.diff(pw[E:]) >= 0.0)),
        "первая запись выше p_b": above[0],
        "max|p_fin - p0|, Па": float(np.max(np.abs(final.p - cfg.initial_conditions.p0))),
        "T[E+1]": T[E + 1],
        "T[E+2]": T[E + 2],
        "T[39] (16 сут)": T[39],
        "T[-1]": T[-1],
        "argmax T после E": E + int(np.argmax(T[E:])),
        "max T после E": float(np.max(T[E:])),
        "min diff T после E": float(np.min(np.diff(T[E:]))),
        "Rs(r_w)[E+1]": rs[E + 1],
        "Rs(r_w)[39]": rs[39],
        "Rs(r_w) финал": final.Rs[0],
        "min diff Rs(r_w) после E+1": float(np.min(np.diff(rs[E + 1:]))),
        "max(Rs - Rs_eq) финал": float(np.max(final.Rs - rs_eq)),
        "max|Rs[43] - Rs фин|": float(np.max(np.abs(st[43].Rs - final.Rs))),
        "газовых ячеек: E, E+1, 39, финал": (n_gas[E], n_gas[E + 1], n_gas[39], n_gas[-1]),
        "n_gas не растёт после E": bool(np.all(np.diff(n_gas[E:]) <= 0)),
        "первая запись без двухфазных после E": next(
            (n for n in range(E, len(st)) if np.all(st[n].regime == 2)), None),
        "ΔE, Дж (E → конец)": float(bal["delta_E"][-1] - bal["delta_E"][E]),
        "адиаб., Дж (E → конец)": float(bal["cum_adiab"][-1] - bal["cum_adiab"][E]),
        "дегаз., Дж (E → конец)": float(bal["cum_deg"][-1] - bal["cum_deg"][E]),
        "JT + конв., Дж (E → конец)": float(abs(bal["cum_jt"][-1] - bal["cum_jt"][E])
                                         + abs(bal["cum_conv"][-1] - bal["cum_conv"][E])),
        "ΔE, Дж (сутки 16: E → 39)": float(bal["delta_E"][39] - bal["delta_E"][E]),
        "адиаб., Дж (E → 39)": float(bal["cum_adiab"][39] - bal["cum_adiab"][E]),
        "дегаз., Дж (E → 39)": float(bal["cum_deg"][39] - bal["cum_deg"][E]),
    }
    gas = final.Sg > 0.0
    if gas.any():
        rr = grid.r_centers
        dT = final.T - cfg.initial_conditions.T0
        k = int(np.argmax(dT))
        out["кольцо газа финал, м"] = (float(rr[gas].min()), float(rr[gas].max()))
        out["max ΔT финал, К (r)"] = (float(dT[k]), float(rr[k]))
    return out


def main():
    h0 = float(sys.argv[1])
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}; h0 = {h0:g} с", flush=True)
    for name in ("16_well_shut_in", "17_shut_in_strong_cooling"):
        cfg, grid, h_base, _ = run(name, None)
        nb = numbers(name, cfg, grid, h_base)
        cfg, grid, h_ramp, stats = run(name, h0)
        nr = numbers(name, cfg, grid, h_ramp)
        print(f"=== {name}: нарастаний {len(stats['ramps'])} "
              f"(t, dt, m, h): {stats['ramps']}; подшагов {stats['ok']}, отказов {stats['fail']}",
              flush=True)
        for key in nb:
            a, b = nb[key], nr[key]
            if isinstance(a, float):
                print(f"  {key:42s} {a:18.10g} → {b:18.10g}  (Δ {b - a:+.4g})")
            else:
                print(f"  {key:42s} {str(a):>18s} → {str(b):>18s}")
        # Строки таблицы «Ожидаемое поведение» README: штатно → с нарастанием
        print("  таблица README: запись | p(r_w), МПа | T(r_w), К | S_g(r_w) | ячеек с газом")
        for n in (0, 1, 15, 16, 17, 22, 27, 39, 43, 53):
            a, b = h_base.states[n], h_ramp.states[n]
            print(f"    {n:2d} | {a.p[0] / 1e6:.4f} → {b.p[0] / 1e6:.4f} | "
                  f"{a.T[0]:.4f} → {b.T[0]:.4f} | {a.Sg[0]:.4f} → {b.Sg[0]:.4f} | "
                  f"{int(np.count_nonzero(a.Sg > 0))} → {int(np.count_nonzero(b.Sg > 0))}")


if __name__ == "__main__":
    main()
