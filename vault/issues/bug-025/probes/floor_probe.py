"""BUG-025 (планирование): предел округления невязки на первом шаге останова.

Сценарий tests/data/bug020_rs150 (N = 350, R_ext = 200 м): 10 сут добычи при 3 МПа,
затем q_oil = 0. Конец добычи считается один раз, дальше первый шаг останова длины
dt решается прямо моделью прототипа (advance и Ньютон ступени 1 отдельно).

Гипотеза: невязка (M^{n+1} - M^n)/dt + q (м³ст/с) стоит на пределе округления ~eps*M_max/dt, при
малом dt он выше абсолютного допуска 1e-11 м³ст/с. Проверки: |F|*dt на остановке
Ньютона постоянен по dt; максимум |F| — в крупных (внешних) ячейках; граница dt
растёт с M_max (R_ext).

Режимы (запуск из numerical_solver/, P — путь к скрипту):
    .venv\\Scripts\\python P scan [R_ext]        без правки: отчёты advance и ход Ньютона ступени 1
    .venv\\Scripts\\python P fix KAPPA [R_ext]   то же с пределом округления в допуске max(1e-11, KAPPA*eps*M_max/dt)
    .venv\\Scripts\\python P series KAPPA k1 k2  с пределом округления: первый час нарастающими шагами
                                                  (dt_series.py VAL-004, m = 9), R_s(r_w) на 1 ч;
                                                  KAPPA = 0 — без подмены (код как есть)
    .venv\\Scripts\\python P repro KAPPA n dt    Simulator: добыча + n интервалов останова по dt
    .venv\\Scripts\\python P nabor KAPPA dt ...  прототип: Nabor_1b (тесты прототипа), N = 12 и 8
Допуск с пределом округления подставляется заменой методов класса RadialBlackOilModel — прототип не правится.
"""
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

# Код — из каталога запуска (основной или worktree), а не из установки в общий venv
SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory   # noqa: E402
from gpn_multiphase_solver.io.config import load_config       # noqa: E402
import radial_blackoil                                         # noqa: E402
from radial_blackoil import blackoil as bo                     # noqa: E402
from radial_blackoil.state import BlackOilState                # noqa: E402

print(f"Код: {SOLVER}")
print(f"Прототип: {radial_blackoil.__file__}")

CFG = SOLVER / "tests" / "data" / "bug020_rs150" / "config.json"
EPS = float(np.finfo(float).eps)
BAR = 1e5
ATOL = 1e-11
# Первый шаг останова: ряд VAL-004 (3600/2**(9+k), k = 4..7) и короче
DTS = (0.439453125, 0.2197265625, 0.10986328125, 0.054931640625, 0.0274658203125,
       0.01, 1e-3, 1e-4)


def m_max(model, state_old):
    """Наибольший запас ячейки старого слоя в масштабе строк невязки: нефть, газ / s_g, м³ст."""
    oi0, gi0 = model._old_inventories(state_old)
    return max(float(np.max(np.abs(oi0))), float(np.max(np.abs(gi0))) / model.gas_residual_scale)


def patch(kappa):
    """Предел округления в допуске обоих Ньютонов: atol -> max(atol, kappa*eps*M_max/dt) (вариант 2)."""
    fixed, switching = bo.RadialBlackOilModel._newton_fixed_active_set, bo.RadialBlackOilModel._newton_switching

    def _fixed(self, z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=ATOL):
        atol = max(atol_sm3s, kappa * EPS * m_max(self, state_old) / float(dt_s))
        return fixed(self, z0, state_old, dt_s, gas_active, max_iter=max_iter, rtol=rtol, atol_sm3s=atol)

    def _switching(self, state_old, dt_s, max_iter=40, rtol=1e-8, atol_sm3s=ATOL, **kw):
        atol = max(atol_sm3s, kappa * EPS * m_max(self, state_old) / float(dt_s))
        return switching(self, state_old, dt_s, max_iter=max_iter, rtol=rtol, atol_sm3s=atol, **kw)

    bo.RadialBlackOilModel._newton_fixed_active_set = _fixed
    bo.RadialBlackOilModel._newton_switching = _switching


def end_of_production(r_ext=None):
    """Модель прототипа и её состояние на конец 10 сут добычи; управление — останов q_oil = 0."""
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    if r_ext is not None:
        cfg.geometry.R_ext = float(r_ext)
    shut = cfg.time.history[10]
    cfg.time.history = cfg.time.history[:10]
    sim, s0 = SimulatorFactory.from_config(cfg)
    t0 = time.perf_counter()
    st = sim.run(s0).states[-1]
    model = sim._hydro._model
    # как адаптер (prototype_adapter.py, шаг 1): м³ст/сут и бар
    model.set_oil_rate_control(shut.q_oil * 86400.0, shut.min_bhp / BAR)
    state = BlackOilState(pressure_bar=st.p / BAR, rs_sm3_sm3=st.Rs.copy(), sg=st.Sg.copy(),
                          gas_active=(st.regime == 1))
    print(f"R_ext = {cfg.geometry.R_ext:g} м, N = {model.grid.n}: добыча {time.perf_counter() - t0:.1f} с; "
          f"двухфазных {int(np.sum(state.gas_active))}, max S_g = {state.sg.max():.3f}")
    return model, state


def scan(model, state):
    n = model.grid.n
    oi0, gi0 = model._old_inventories(state)
    M = m_max(model, state)
    print(f"запасы: нефть max {oi0.max():.4e} м³ст (ячейка {int(np.argmax(oi0))}), "
          f"газ/s_g max {gi0.max() / model.gas_residual_scale:.4e} (ячейка {int(np.argmax(gi0))}), "
          f"s_g = {model.gas_residual_scale:g}; eps*M_max = {EPS * M:.3e} м³ст; "
          f"eps*M_max/atol = {EPS * M / ATOL:.3f} с")
    for dt in DTS:
        # ── advance целиком: итог и отчёт (при отказе — Ньютона ступени 1, DEBT-030) ──
        t0 = time.perf_counter()
        new, rep = model.advance(state.copy(), dt)
        el = time.perf_counter() - t0
        stage = 4 if rep.phase_switching else 3 if rep.globalized else 2 if rep.fallback else 1
        print(f"dt = {dt:.4e} с: advance {'сошёлся' if rep.converged else 'НЕ сошёлся'} "
              f"(ступень {stage}, {el:.1f} с), выход {rep.exit_reason!r}, итераций {rep.iterations}, "
              f"|F| = {rep.residual_inf:.3e}, допуск {rep.residual_tol if rep.residual_tol is None else f'{rep.residual_tol:.3e}'}, "
              f"|F|*dt = {rep.residual_inf * dt:.3e}, предел округления eps*M/dt = {EPS * M / dt:.3e}")
        # ── Ньютон ступени 1 отдельно: норма и ячейка максимума на каждом приближении ──
        trace = []
        fd = model.finite_difference_jacobian

        def traced(z, so, d, ga, *a, **k):
            J, f = fd(z, so, d, ga, *a, **k)
            i = int(np.argmax(np.abs(f)))
            trace.append((float(np.max(np.abs(f))), i % n, "н" if i < n else "г"))
            return J, f

        model.finite_difference_jacobian = traced
        try:
            mask = state.gas_active.copy()
            z, r1 = model._newton_fixed_active_set(model.pack(state, mask), state, dt, mask)
        finally:
            del model.finite_difference_jacobian
        f = model.residual(z, state, dt, mask)
        i = int(np.argmax(np.abs(f)))
        steps = " → ".join(f"{a:.2e}[{c}{b}]" for a, b, c in trace)
        print(f"    ступень 1: {r1.exit_reason}, итераций {r1.iterations}; |F| по итерациям: {steps} → "
              f"итог {np.max(np.abs(f)):.2e}[{'н' if i < n else 'г'}{i % n}]")


def series(kappa, k1, k2):
    spec = importlib.util.spec_from_file_location(
        "dt_series", SOLVER.parent / "vault" / "issues" / "val-004" / "probes" / "dt_series.py")
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    for k in range(k1, k2 + 1):
        t0 = time.perf_counter()
        out, el, acc, nf, h = ds.run(1, k, 9)
        sub = ", ".join(f"{a:g}×{b}" for a, b in sorted(acc.items()))
        print(f"k={k} первый шаг {3600 / 2 ** (9 + k):.5f} с | 1 ч: R_s(r_w) = {out['1h_Rs'][0]:.7f}, "
              f"p(r_w) = {out['1h_p'][0] / BAR:.7f} бар, T(r_w) = {out['1h_T'][0]:.7f} К | отказов {nf}; "
              f"подшаги: {sub}; счёт {time.perf_counter() - t0:.1f} с", flush=True)


def repro(n, dt):
    """Simulator: 10 сут добычи + n интервалов останова по dt (каждый — один шаг, если сошёлся)."""
    import copy
    from gpn_multiphase_solver.hydro.base import HydroConvergenceError
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    prod, shut = cfg.time.history[:10], cfg.time.history[10]
    tail = []
    for _ in range(n):
        x = copy.deepcopy(shut)
        x.dt = dt
        tail.append(x)
    cfg.time.history = list(prod) + tail
    sim, s0 = SimulatorFactory.from_config(cfg)
    fails, msgs = [], []
    solve = sim._hydro.solve

    def counting(state, h, bc):
        try:
            return solve(state, h, bc)
        except HydroConvergenceError as exc:
            fails.append((state.t - 10 * 86400.0, h))
            msgs.append(str(exc))
            raise

    sim._hydro.solve = counting
    t0 = time.perf_counter()
    try:
        hist = sim.run(s0)
        res = f"прошёл, R_s(r_w) = {hist.states[-1].Rs[0]:.7f}"
    except RuntimeError:
        res = "ОТКАЗ расчёта"
    print(f"останов {n} × {dt:g} с: {res}; отказов гидродинамики {len(fails)}"
          + (f", первый на t − 10 сут = {fails[0][0]:.4g} с, dt = {fails[0][1]:.4g} с" if fails else "")
          + f"; счёт {time.perf_counter() - t0:.1f} с")
    if msgs:
        print(f"    первый отказ: {msgs[0]}")


def nabor(dts):
    """Тесты прототипа: Nabor_1b (N = 12, отбор 200 -> 100 бар), один Ньютон и advance при малых dt."""
    from radial_blackoil.input_reader import load_input
    from radial_blackoil.grid import RadialGrid
    from radial_blackoil.rock import CompressibleRock
    proto = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
    for n in (12, 8):
        inp = load_input(proto / "tests" / "fixtures" / "Nabor_1b.xlsx")
        p = inp.params
        g = RadialGrid(float(p['Well radius rw']), float(p['Outer radius re']), float(p['Formation thickness h']),
                       n, float(p['Absolute permeability']))
        r = CompressibleRock(float(p['Reference porosity']), float(p['Reference pressure']),
                             float(p['Rock compressibility cr']))
        m = bo.RadialBlackOilModel(g, r, inp.pvt, inp.relperm, 100.0, float(p['Outer-boundary pressure']),
                                   float(p['Initial dissolved gas Rs']), skin=float(p['Well skin']))
        s = BlackOilState.undersaturated(g.n, 200.0, float(p['Initial dissolved gas Rs']))
        M = m_max(m, s)
        print(f"Nabor_1b N = {n}: M_max = {M:.4e} м³ст, eps*M_max/atol = {EPS * M / ATOL:.4g} с")
        for dt in dts:
            z, r1 = m._newton_fixed_active_set(m.pack(s), s, dt, s.gas_active)
            _, ra = m.advance(s.copy(), dt)
            print(f"    dt = {dt:g} с: Ньютон {r1.exit_reason}, итераций {r1.iterations}, |F| = {r1.residual_inf:.3e}, "
                  f"допуск {r1.residual_tol:.3e}, |F|*dt = {r1.residual_inf * dt:.3e}; advance "
                  f"{'сошёлся' if ra.converged else 'НЕ сошёлся'} ({ra.exit_reason})")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode in ("repro", "nabor"):
        if float(sys.argv[2]) > 0:
            patch(float(sys.argv[2]))
        print(f"предел округления в допуске: kappa = {sys.argv[2]}" + (" (без подмены)" if float(sys.argv[2]) == 0 else ""))
        if mode == "repro":
            repro(int(sys.argv[3]), float(sys.argv[4]))
        else:
            nabor([float(x) for x in sys.argv[3:]])
        sys.exit(0)
    if mode == "scan":
        scan(*end_of_production(sys.argv[2] if len(sys.argv) > 2 else None))
    elif mode == "fix":
        patch(float(sys.argv[2]))
        print(f"предел округления в допуске: kappa = {sys.argv[2]}")
        scan(*end_of_production(sys.argv[3] if len(sys.argv) > 3 else None))
    elif mode == "series":
        # KAPPA = 0 — без подмены методов: код как есть
        if float(sys.argv[2]) > 0:
            patch(float(sys.argv[2]))
        print(f"предел округления в допуске: kappa = {sys.argv[2]}" + (" (без подмены)" if float(sys.argv[2]) == 0 else ""))
        series(float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    else:
        sys.exit(__doc__)
