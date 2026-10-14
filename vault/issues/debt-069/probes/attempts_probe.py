"""DEBT-069 (/plan-improve): какие попытки ступеней advance теряет отчёт общего отказа.

Перехват _advance_phases на экземпляре модели (как подмены тестов DEBT-030): каждый
вызов — одна попытка; ступень — по флагам модели в момент вызова (ступень 1: граница
S_g = -0.05; 2: без границы; 3: ||F||_2; 4: _phase_switching). Пакет не правится.
Печать: попытки по порядку, итоговый отчёт advance (что видно сейчас) и черновик строки
попыток для текста отказа — длина строки в символах.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P bug018                — BUG-018, N = 350, шаг 86400 с (тест DEBT-054)
    .venv\\Scripts\\python P example <пример> <dt, с> ...  — первый шаг примера при управлении по p_wf
"""

import sys
from dataclasses import replace
from pathlib import Path

SOLVER_ROOT = Path.cwd()
assert (SOLVER_ROOT / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
# Код решателя и прототипа — из каталога запуска (основной или worktree): установленный
# radial_blackoil указывает на основной каталог, и из worktree без этой строки брался бы он
sys.path[:0] = [str(SOLVER_ROOT), str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")]
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.hydro.prototype_adapter import _EXIT_REASONS  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

BRANCH = {"open": "открыта", "shut": "закрыта", "": "", None: ""}


def stage_of(m):
    """Ступень по флагам модели в момент вызова _advance_phases."""
    if m._phase_switching:
        return 4
    if m._line_search_l2:
        return 3
    if m._sg_lower_bound is None:
        return 2
    return 1


def install(m):
    """Перехват _advance_phases: список (ступень, ветка, снимок отчёта, p[0] нового состояния)."""
    log = []
    orig = m._advance_phases

    def wrapped(state_old, dt_s, *a, **kw):
        new, rep = orig(state_old, dt_s, *a, **kw)
        log.append((stage_of(m), m._well_branch or "", replace(rep), float(new.pressure_bar[0])))
        states.append(new.copy())
        return new, rep

    states = []
    m._probe_states = states

    m._advance_phases = wrapped
    return log


def line(stage, branch, rep, verdict=None):
    """Черновик записи попытки: «2 открыта — набор фаз не установился (31 ит., 12 пр., 364 перекл.)»."""
    reason = verdict or rep.exit_reason
    head = f"{stage}{(' ' + BRANCH[branch]) if branch else ''}"
    if rep.converged and verdict is None:
        return f"{head} — сошлась ({rep.iterations} ит.)"
    return (f"{head} — {_EXIT_REASONS.get(reason, reason)} ({rep.iterations} ит., "
            f"{rep.active_set_iterations} пр., {rep.phase_switches} перекл., невязка {rep.residual_inf:.1e})")


def report(m, log, final, target):
    """Попытки, итоговый отчёт и черновик строки."""
    parts = []
    for stage, branch, rep, p0 in log:
        # Вердикт ветки: сошлась, но несогласована — как в _fallback (DEBT-040)
        verdict = None
        if branch and rep.converged and not ((p0 >= target) if branch == "open" else (p0 <= target)):
            verdict = "branch"
        print(f"    ступень {stage} {branch or '-':5s} сошлась={rep.converged!s:5s} выход={rep.exit_reason:12s} "
              f"итераций {rep.iterations:3d} проходов {rep.active_set_iterations:3d} переключений {rep.phase_switches:4d} "
              f"невязка {rep.residual_inf:.2e} мера {rep.cell_measure if rep.cell_measure is None else f'{rep.cell_measure:.2e}'} "
              f"p[0] = {p0:.2f}{'  -> несогласована' if verdict else ''}")
        parts.append(line(stage, branch, rep, verdict))
    print(f"  итог advance: сошлась={final.converged} выход={final.exit_reason} итераций {final.iterations} "
          f"невязка {final.residual_inf:.2e} ветка={final.well_branch!r} смен={final.well_switches} "
          f"fallback={final.fallback} globalized={final.globalized} phase_switching={final.phase_switching}")
    # После DEBT-069: попытки отчёта advance против перехвата (ступень, ветка, выход с вердиктом, итерации)
    att = getattr(final, "attempts", None)
    if att is not None:
        seen = [(s, b, "branch" if (b and r.converged and not ((p >= target) if b == "open" else (p <= target)))
                 else r.exit_reason, r.iterations) for s, b, r, p in log]
        got = [(a.stage, a.branch, a.report.exit_reason, a.report.iterations) for a in att]
        print(f"  attempts отчёта ({len(got)}) = перехват ({len(seen)}): {got == seen}")
    text = "попытки: " + "; ".join(parts)
    print(f"  черновик ({len(text)} симв.): {text}")
    short = [p for p, (_, b, r, _) in zip(parts, log) if not (b == "shut" and r.iterations == 0)]
    text2 = "попытки: " + "; ".join(short)
    print(f"  без «закрыта» за 0 ит. ({len(text2)} симв.): {text2}")
    # Ступень 2 «открыта» против ступени 1: побитово ли совпали состояние и числа отчёта
    import numpy as np
    st = m._probe_states
    for k, (stage, branch, rep, _) in enumerate(log):
        if stage == 2 and branch == "open":
            r1, s1, s2 = log[0][2], st[0], st[k]
            same_state = all(np.array_equal(getattr(s1, f), getattr(s2, f))
                             for f in ("pressure_bar", "sg", "rs_sm3_sm3", "gas_active"))
            same_rep = ((r1.iterations, r1.active_set_iterations, r1.phase_switches, r1.residual_inf,
                         r1.exit_reason, r1.cell_measure)
                        == (rep.iterations, rep.active_set_iterations, rep.phase_switches, rep.residual_inf,
                            rep.exit_reason, rep.cell_measure))
            print(f"  ступень 2 «открыта» против ступени 1: состояние побитово {same_state}, "
                  f"числа отчёта побитово {same_rep}")


def bug018():
    cfg = load_config(SOLVER_ROOT / "tests" / "data" / "bug018_rs500" / "config.json")
    cfg.output.log_level = "ERROR"
    cfg.grid.N = 350
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    m = sim._hydro._model
    m.set_bhp_control(sim._schedule.intervals[0].bc.well.p_wf / 1e5)
    ps = BlackOilState(pressure_bar=init.p / 1e5, rs_sm3_sm3=init.Rs.copy(),
                       sg=init.Sg.copy(), gas_active=(init.regime == 1))
    log = install(m)
    _, rep = m.advance(ps, dt)
    print(f"bug018 N = 350, dt = {dt:g} с, p_wf = {m.p_bhp_bar:.2f} бар, p_ext = {m.p_outer_bar:.2f} бар")
    report(m, log, rep, float(m.p_bhp_bar))


def example(name, dts):
    for dt in dts:
        cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, s0 = SimulatorFactory.from_config(cfg)
        ad = sim._hydro
        m = ad._model
        m.set_bhp_control(cfg.time.history[0].p_wf / 1e5)
        old = BlackOilState(pressure_bar=s0.p / 1e5, rs_sm3_sm3=s0.Rs.copy(),
                            sg=s0.Sg.copy(), gas_active=(s0.regime == 1))
        log = install(m)
        _, rep = m.advance(old, dt, max_active_iter=ad._max_active_iter, max_newton=ad._max_newton)
        print(f"{name} dt = {dt:g} с, p_wf = {m.p_bhp_bar:.2f} бар, p_ext = {m.p_outer_bar:.2f} бар")
        report(m, log, rep, float(m.p_bhp_bar))


if __name__ == "__main__":
    mode = sys.argv[1]
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}")
    import radial_blackoil
    print(f"прототип: {Path(radial_blackoil.__file__).parent}")
    if mode == "bug018":
        bug018()
    elif mode == "example":
        example(sys.argv[2], [float(a) for a in sys.argv[3:]])
