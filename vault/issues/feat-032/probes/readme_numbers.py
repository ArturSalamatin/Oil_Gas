"""FEAT-032: числа README и тестов примеров 16 и 17 (останов) — для правки после нарастания шага.

Режимы:
  без аргумента — конфиги примеров как есть (после реализации FEAT-032 в них
                  time.dt_after_control_change = 2): числа самой реализации;
  <h0>          — планирование: конфиги без поля + эмуляция варианта 2
                  (ramp_probe.patch, первый интервал сменой не считается).
Оба режима обязаны дать одни и те же числа и отпечатки (fingerprint_examples.py).

Печатает: отпечаток; строки таблиц «Ожидаемое поведение»; числа абзацев README
(давление, T, R_s, газ, профили на финале); члены баланса энергии за первые
сутки останова и за весь останов (все шесть, как таблица README 17).
Консольные блоки main.py (баланс массы, проверка R_s) — запуском main.py.

Запуск из numerical_solver/ (P — путь к скрипту): .venv\\Scripts\\python P [h0]
"""

import sys
import time
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

E = 15
TERMS = ("delta_E", "cum_adiab", "cum_deg", "cum_jt", "cum_conv", "cum_cond")


def at(r, prof, x):
    """Значение профиля в ячейке, ближайшей к радиусу x, м."""
    return float(prof[int(np.argmin(np.abs(r - x)))])


def main():
    h0 = float(sys.argv[1]) if len(sys.argv) > 1 else None
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}; "
          f"{'конфиг как есть' if h0 is None else f'эмуляция, h0 = {h0:g} с'}", flush=True)
    for name in ("16_well_shut_in", "17_shut_in_strong_cooling"):
        cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        print(f"=== {name}: time.dt_after_control_change = "
              f"{getattr(cfg.time, 'dt_after_control_change', 'нет поля')}", flush=True)
        sim, s0 = SimulatorFactory.from_config(cfg)
        if h0 is not None:
            patch(sim, h0, include_first=False)
        # Приток через контур на первом принятом подшаге останова: G_o[N] < 0 —
        # к скважине (конвенция: > 0 — от скважины), README 16 — «3.4e-3 м³ст/с»
        first = {}
        solve = sim._hydro.solve

        def solve_first(state, dt, bc):
            res = solve(state, dt, bc)
            if state.t >= E * 86400.0 - 1e-6 and "G" not in first:
                first.update(G=float(res.G_o[-1]), dt=dt)
            return res

        sim._hydro.solve = solve_first
        t_run = time.perf_counter()
        hist = sim.run(s0)
        t_run = time.perf_counter() - t_run
        grid, st = sim._grid, hist.states
        print(f"  счёт {t_run:.1f} с; первый подшаг останова {first['dt']:.4g} с, "
              f"G_o на контуре {first['G']:+.4e} м³ст/с")
        r = grid.r_centers
        pvt = _create_pvt(cfg)
        T0, p0, Rs0 = (cfg.initial_conditions.T0, cfg.initial_conditions.p0,
                       cfg.initial_conditions.Rs0)
        pb = float(pvt.pb(np.array([Rs0]))[0])
        pw = np.array([s.p[0] for s in st])
        T = np.array([s.T[0] for s in st])
        print(f"  отпечаток {fingerprint(hist)}")
        print("  таблица: запись | p(r_w), МПа | T(r_w), К | S_g(r_w) | ячеек с газом")
        for n in (0, 1, 15, 16, 17, 22, 26, 27, 39, 41, 43, 53):
            s = st[n]
            print(f"    {n:2d} | {s.p[0] / 1e6:.4f} | {s.T[0]:.4f} | {s.Sg[0]:.4f} | "
                  f"{int(np.count_nonzero(s.Sg > 0))}")
        print(f"  p_b = {pb / 1e6:.4f} МПа; p[26] - p_b = {(pw[26] - pb) / 1e3:+.1f} кПа; "
              f"p[27] - p_b = {(pw[27] - pb) / 1e3:+.1f} кПа")
        dp = np.diff(pw[E:])
        print(f"  наименьшее приращение p(r_w) после E: {dp.min():.3g} Па; "
              f"финал max|p - p0| = {np.max(np.abs(st[-1].p - p0)):.3g} Па")
        k = E + int(np.argmax(T[E:]))
        print(f"  T(r_w): E {T[E]:.4f}; +1 ч {T[E + 1]:.4f} (+{T[E + 1] - T[E]:.4f}); "
              f"+2 ч {T[E + 2]:.4f}; 16 сут {T[39]:.4f}; 30 сут {T[-1]:.4f}; "
              f"максимум после E — запись {k}, {T[k]:.4f}; "
              f"недогрев: 16 сут {T0 - T[39]:.3f}, 30 сут {T0 - T[-1]:.3f} К")
        dT = np.diff(T[E:])
        print(f"  приращения T(r_w) после E: min {dT.min():.4g}, max {dT.max():.4g}; "
              f"после максимума max {np.diff(T[k:]).max() if k < len(T) - 1 else float('nan'):.4g}")
        f = st[-1]
        print(f"  финал T - T0: r_w {f.T[0] - T0:+.3f}, 1 м {at(r, f.T, 1.0) - T0:+.3f}, "
              f"10 м {at(r, f.T, 10.0) - T0:+.3f}, 22.5 м {at(r, f.T, 22.5) - T0:+.3f}, "
              f"25 м {at(r, f.T, 25.0) - T0:+.3f}; max {np.max(f.T - T0):+.4f} на "
              f"{r[int(np.argmax(f.T - T0))]:.2f} м; min {np.min(f.T - T0):+.3f} на "
              f"{r[int(np.argmin(f.T - T0))]:.2f} м")
        print(f"  финал R_s: r_w {f.Rs[0]:.4f}, 0.3 м {at(r, f.Rs, 0.3):.1f}, 1 м {at(r, f.Rs, 1.0):.1f}; "
              f"диапазон {f.Rs.min():.4f} … {f.Rs.max():.4f}; ячеек R_s > R_s0: "
              f"{int(np.count_nonzero(f.Rs > Rs0))}")
        s1 = st[E + 1]
        gas1 = s1.Sg > 0
        print(f"  1 ч останова: ячеек с газом {int(gas1.sum())}, газ с r = "
              f"{r[gas1].min() if gas1.any() else float('nan'):.3f} м; R_s(r_w) {s1.Rs[0]:.4f}")
        gas = f.Sg > 0
        if gas.any():
            print(f"  финал: кольцо газа {r[gas].min():.2f}–{r[gas].max():.2f} м, "
                  f"{int(gas.sum())} ячеек, S_g до {f.Sg.max():.4f} на {r[int(np.argmax(f.Sg))]:.1f} м")
        bal = compute_balance(hist, grid, cfg)
        for lab, a, b in (("первые сутки останова", E, 39), ("весь останов", E, len(st) - 1),
                          ("добыча", 0, E)):
            print(f"  баланс энергии, {lab}, Дж: " + ", ".join(
                f"{t} {float(bal[t][b] - bal[t][a]):+.4g}" for t in TERMS))
        if name.startswith("17"):
            # README 17, «Шаг интегрирования и время расчёта»: тот же пример при
            # dt_integration = 1 сут (первые сутки останова всё равно по часам)
            cfg.time.dt_integration = 86400.0
            sim, s0 = SimulatorFactory.from_config(cfg)
            if h0 is not None:
                patch(sim, h0, include_first=False)
            t_run = time.perf_counter()
            hd = sim.run(s0)
            print(f"  dt_integration = 1 сут: счёт {time.perf_counter() - t_run:.1f} с, "
                  f"T(r_w) на 30 сут {hd.states[-1].T[0]:.4f} К")


if __name__ == "__main__":
    main()
