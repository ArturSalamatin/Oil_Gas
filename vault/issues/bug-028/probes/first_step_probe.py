"""BUG-028 (/issue): первый шаг добычи из равновесия длиной dt — сходится ли.

Режим single: один шаг dt от t = 0 без дробления (numerics.max_retries = 0) —
сходится ли advance на шаге dt сам по себе. Режим split: один шаг dt со
штатным дроблением (max_retries = 9) — проходит ли шаг и какой ценой.
Пакет не правится: меняется только конфиг примера в памяти.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P single <пример> <dt, с> ...
    .venv\\Scripts\\python P split <пример> <dt, с>
    .venv\\Scripts\\python P stages <пример> <dt, с> ...   — ступени 1–4 по отдельности
    .venv\\Scripts\\python P aset <пример> <K> <dt, с> ...  — single при max_active_set_iter = K
    .venv\\Scripts\\python P co <пример> <c_o, 1/Па> <dt, с> ... — single при pvt.co_undersaturated = c_o
    .venv\\Scripts\\python P passes <пример> <K> <dt, с> ...  — ступень 1 при K проходах набора фаз
    .venv\\Scripts\\python P v1 <пример> <N|0> <dt, с> ...  — single с вариантом 1 (variant1.py)
"""

import copy
import sys
import time
from pathlib import Path

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def one_step(name, dt, max_retries, log_level, max_aset=None, co=None, n_grid=None):
    """Конфиг примера, сокращённый до одного шага dt от t = 0 при том же управлении."""
    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    if n_grid is not None:
        cfg.grid.N = n_grid
    first = copy.deepcopy(cfg.time.history[0])
    first.dt = dt
    cfg.time.history = [first]
    cfg.time.dt_integration = dt
    cfg.numerics.max_retries = max_retries
    if max_aset is not None:
        # numerics.max_active_set_iter: проходов набора фаз ступеней 1–3 (умолчание 12)
        cfg.numerics.max_active_set_iter = max_aset
    if co is not None:
        # pvt.co_undersaturated: сжимаемость недонасыщенной нефти Стендинга (умолчание 0)
        cfg.pvt.co_undersaturated = co
    cfg.output.log_level = log_level
    sim, s0 = SimulatorFactory.from_config(cfg)
    t0 = time.perf_counter()
    try:
        hist = sim.run(s0)
    except RuntimeError as exc:
        # Хвост текста — отказ гидродинамики последнего подшага (DEBT-054)
        tail = str(exc).split("Последний отказ гидродинамики: ")[-1]
        return f"ОТКАЗ, {time.perf_counter() - t0:.1f} с — {tail}"
    st = hist.states[-1]
    n_two = int((st.regime == 1).sum())
    return (f"сошёлся, {time.perf_counter() - t0:.1f} с — p(r_w) = {st.p[0] / 1e5:.2f} бар, "
            f"S_g(r_w) = {st.Sg[0]:.3f}, двухфазных ячеек {n_two}")


def stages(name, dt):
    """Ступени 1–4 advance по отдельности на первом шаге dt и ход набора фаз ступени 1."""
    import numpy as np
    from radial_blackoil.state import BlackOilState

    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    ad = sim._hydro
    m = ad._model
    m.set_bhp_control(cfg.time.history[0].p_wf / 1e5)
    old = BlackOilState(pressure_bar=s0.p / 1e5, rs_sm3_sm3=s0.Rs.copy(),
                        sg=s0.Sg.copy(), gas_active=(s0.regime == 1))
    lim = dict(max_active_iter=ad._max_active_iter, max_newton=ad._max_newton)
    # p_b(R_s0) — обращение rs_sat(p) делением пополам; c_o — сжимаемость
    # недонасыщенной нефти при p0, R_s0 по B_o прототипа, c_r — породы из конфига
    p0, rs0 = float(old.pressure_bar[0]), float(old.rs_sm3_sm3[0])
    lo, hi = 1.0, p0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if float(m.pvt.rs_sat(np.array([mid]))[0]) < rs0 else (lo, mid)
    bo = lambda p: float(m.pvt.bo(np.array([p]), np.array([rs0]))[0])
    c_o = -(bo(p0 + 0.5) - bo(p0 - 0.5)) / bo(p0) / 1e5
    print(f"{name} dt = {dt:g} с: p0 = {p0:.2f} бар, R_s0 = {rs0:g}, p_b = {lo:.2f} бар, "
          f"p_wf = {m.p_bhp_bar:.2f} бар, (p0 - p_b)/(p0 - p_wf) = {(p0 - lo) / (p0 - m.p_bhp_bar):.3f}, "
          f"c_o = {c_o:.2e} 1/Па, c_r = {cfg.rock.compressibility:g} 1/Па, лимиты {lim}", flush=True)

    # ── Ступень 1: цикл набора фаз _advance_phases, повторён с печатью каждого прохода ──
    st = old.copy(); mask = st.gas_active.copy(); guess = st.copy()
    for aset in range(1, lim["max_active_iter"] + 1):
        z, rep = m._newton_fixed_active_set(m.pack(guess, mask), st, dt, mask, max_iter=lim["max_newton"])
        if not rep.converged:
            print(f"  ст.1 проход {aset}: Ньютон не сошёлся ({rep.exit_reason}, итераций {rep.iterations})")
            break
        trial = m.unpack(z, mask); rs_sat = m.pvt.rs_sat(trial.pressure_bar)
        act = (~mask) & (trial.rs_sm3_sm3 > rs_sat + m.rs_switch_tol)
        deact = mask & (trial.sg < -m.sg_switch_tol)
        ia, idd = np.flatnonzero(act), np.flatnonzero(deact)
        two = np.flatnonzero(mask)
        print(f"  ст.1 проход {aset}: итераций {rep.iterations}, двухфазных {two.size}"
              f"{f' (ячейки {two.min()}…{two.max()})' if two.size else ''}, p(r_w) = {trial.pressure_bar[0]:.2f} бар; "
              f"включить {ia.size}{f' ({ia.min()}…{ia.max()})' if ia.size else ''}, "
              f"выключить {idd.size}{f' ({idd.min()}…{idd.max()}, min S_g = {trial.sg[deact].min():.2e})' if idd.size else ''}",
              flush=True)
        if ia.size + idd.size == 0:
            print("  ст.1: набор фаз установился"); break
        newmask = mask.copy(); newmask[act] = True; newmask[deact] = False
        guess = trial.copy(); guess.gas_active = newmask.copy()
        if np.any(act):
            pa = guess.pressure_bar[act]; rtot = guess.rs_sm3_sm3[act].copy(); rsat = m.pvt.rs_sat(pa)
            bo = m.pvt.bo(pa, rsat); bg = m.pvt.bg(pa); d = np.maximum(rtot - rsat, 0.0)
            sg0 = np.maximum(d * bg / (bo + d * bg), 1e-8)
            if m.sg_activation_cap is not None: sg0 = np.minimum(sg0, m.sg_activation_cap)
            guess.sg[act] = sg0; guess.rs_sm3_sm3[act] = rsat
        if np.any(deact):
            guess.sg[deact] = 0.0; guess.rs_sm3_sm3[deact] = m.pvt.rs_sat(guess.pressure_bar[deact])
        mask = newmask

    # ── Ступени 1–4 штатными методами прототипа ──
    def show(tag, rep):
        print(f"  {tag}: {'сошлась' if rep.converged else 'отказ'}, выход {rep.exit_reason}, "
              f"итераций {rep.iterations}, проходов набора фаз {rep.active_set_iterations}, "
              f"переключений {rep.phase_switches}, невязка {rep.residual_inf:.2e}, "
              f"ветвь {getattr(rep, 'well_branch', None)}", flush=True)
    show("ступень 1", m._advance_phases(old, dt, **lim)[1])
    show("ступень 2", m._fallback(old, dt, **lim)[1])
    m._line_search_l2 = True; m._sg_step_max = 0.2
    try:
        show("ступень 3", m._fallback(old, dt, **lim)[1])
    finally:
        m._line_search_l2 = False; m._sg_step_max = None
    show("ступень 4", m.advance_fourth_stage(old, dt, **lim)[1])

    # ── Ветка «открыта» ступеней 2–4 отдельно: _fallback отдаёт отчёт последней
    # ветки («закрыта», 0 итераций), причина отказа «открыта» в нём не видна ──
    def open_branch(tag, l2, switching):
        m._sg_lower_bound = None; m._well_branch = "open"
        m._line_search_l2 = l2; m._sg_step_max = 0.2 if l2 else None; m._phase_switching = switching
        try:
            new, rep = m._advance_phases(old, dt, **lim)
        finally:
            m._sg_lower_bound = -0.05; m._well_branch = None
            m._line_search_l2 = False; m._sg_step_max = None; m._phase_switching = False
        extra = (f", p(r_w) = {new.pressure_bar[0]:.2f} бар, двухфазных {int(new.gas_active.sum())}"
                 if rep.converged else "")
        print(f"  {tag}, ветка open: {'сошлась' if rep.converged else 'отказ'}, выход {rep.exit_reason}, "
              f"итераций {rep.iterations}, проходов {rep.active_set_iterations}, "
              f"переключений {rep.phase_switches}, невязка {rep.residual_inf:.2e}{extra}", flush=True)
    open_branch("ступень 2", False, False)
    open_branch("ступень 3", True, False)
    open_branch("ступень 4", False, True)   # advance_fourth_stage: только _phase_switching


def passes(name, k, dts):
    """Ступень 1 (_advance_phases) с K проходами набора фаз: сколько проходов и итераций нужно."""
    import numpy as np
    from radial_blackoil.state import BlackOilState

    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    m = sim._hydro._model
    m.set_bhp_control(cfg.time.history[0].p_wf / 1e5)
    old = BlackOilState(pressure_bar=s0.p / 1e5, rs_sm3_sm3=s0.Rs.copy(),
                        sg=s0.Sg.copy(), gas_active=(s0.regime == 1))
    for dt in dts:
        t0 = time.perf_counter()
        new, rep = m._advance_phases(old, dt, max_active_iter=k, max_newton=sim._hydro._max_newton)
        print(f"{name} dt = {dt:g} с, ступень 1 при {k} проходах: "
              f"{'сошлась' if rep.converged else 'отказ ' + rep.exit_reason}, проходов {rep.active_set_iterations}, "
              f"итераций {rep.iterations}, переключений {rep.phase_switches}, "
              f"двухфазных {int(np.count_nonzero(new.gas_active))}, {time.perf_counter() - t0:.2f} с", flush=True)


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    mode, name = sys.argv[1], sys.argv[2]
    if mode == "passes":
        passes(name, int(sys.argv[3]), [float(a) for a in sys.argv[4:]])
        return
    if mode == "stages":
        for a in sys.argv[3:]:
            stages(name, float(a))
        return
    if mode == "aset":
        k = int(sys.argv[3])
        for a in sys.argv[4:]:
            print(f"{name} dt = {float(a):g} с, max_active_set_iter = {k}: "
                  f"{one_step(name, float(a), 0, 'ERROR', k)}", flush=True)
        return
    if mode == "v1":
        # Вариант 1 (variant1.py): один шаг без дробления; N сетки — третий аргумент (0 — из конфига)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import variant1
        n_grid = int(sys.argv[3]) or None
        for a in sys.argv[4:]:
            variant1.install(); variant1.EVENTS.clear()
            try:
                res = one_step(name, float(a), 0, 'ERROR', n_grid=n_grid)
            finally:
                variant1.uninstall()
            ev = variant1.EVENTS
            extra = (f"; проходов {max(e['passes'] for e in ev)}, итераций {max(e['newton'] for e in ev)}"
                     if ev else "; за 12 проходов")
            print(f"{name} N = {n_grid or 'конфиг'} dt = {float(a):g} с, вариант 1: {res}{extra}", flush=True)
        return
    if mode == "co":
        co = float(sys.argv[3])
        for a in sys.argv[4:]:
            print(f"{name} dt = {float(a):g} с, co_undersaturated = {co:g} 1/Па: "
                  f"{one_step(name, float(a), 0, 'ERROR', co=co)}", flush=True)
        return
    if mode == "single":
        for a in sys.argv[3:]:
            print(f"{name} dt = {float(a):g} с: {one_step(name, float(a), 0, 'ERROR')}", flush=True)
    elif mode == "split":
        dt = float(sys.argv[3])
        print(f"{name} dt = {dt:g} с, max_retries = 9: {one_step(name, dt, 9, 'INFO')}", flush=True)


if __name__ == "__main__":
    main()
