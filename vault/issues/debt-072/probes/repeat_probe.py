"""DEBT-072 (/plan-improve): как часто первая попытка ступени 2 advance повторяет ступень 1 и сколько она стоит.

Перехват на экземпляре модели прототипа, пакет не правится:
- advance, advance_fourth_stage — время вызова;
- _advance_phases — ступень (по флагам модели в момент вызова), ветка, время, снимок отчёта и состояния;
- _newton_fixed_active_set — в ступени 1: число решений (положительное свидетельство, что ступень считалась);
- _trial_is_reasonable — в ступени 1: пробная точка, которую отвергла только граница S_g = -0.05
  (повторный вызов без границы её принимает);
- _well_fluxes — в ступени 1 при управлении по p_wf: автоматическая ветка дала «закрыта» (p[0] <= p_wf),
  в том числе на возмущённых векторах конечно-разностного якобиана.

«Чистая» ступень 1 (признак варианта 1 плана): решений Ньютона > 0, отказов только по границе 0,
«закрыта» 0. Кандидат на пропуск — первая попытка ступени 2 после отказа ступени 1: ветка «открыта»
при управлении по p_wf, единственная попытка без ветки при управлении по дебиту. Для каждого
кандидата — побитово ли он равен ступени 1 (состояние и числа отчёта).

Итог по сценарию: вызовов advance, отказов ступени 1, кандидатов, из них чистых; совпали побитово
(чистые / нечистые); время всего расчёта, advance (+ ступени 4 по памяти), отказавших advance,
чистых кандидатов — это и есть экономия варианта 1.

Ожидание по построению: каждый чистый кандидат совпадает побитово. Чистый, но не совпавший —
опровержение довода плана, разбирать.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P                     — все сценарии
    .venv\\Scripts\\python P ex19 ex21 bug018    — выбранные
    .venv\\Scripts\\python P t04                 — первый шаг T04 прототипа (в «все» не входит)
"""

import copy
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
# Код решателя и прототипа — из каталога запуска (основной или worktree)
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver import factory as _factory                    # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory              # noqa: E402
from gpn_multiphase_solver.io.config import load_config                 # noqa: E402
import radial_blackoil                                                   # noqa: E402

REP_FIELDS = ("converged", "iterations", "residual_inf", "active_set_iterations", "phase_switches",
              "residual_tol", "cell_measure", "exit_reason", "cell_floor")
STATE_FIELDS = ("pressure_bar", "rs_sm3_sm3", "sg", "gas_active")


def stage_of(m):
    """Ступень по флагам модели в момент вызова (как attempts_probe.py DEBT-069)."""
    if m._phase_switching:
        return 4
    if m._line_search_l2:
        return 3
    if m._sg_lower_bound is None:
        return 2
    return 1


def install(m):
    """Перехваты; возвращает накопитель статистики."""
    st = dict(advance=0, advance_t=0.0, stage4_mem=0, stage4_mem_t=0.0, failed1=0, failed_adv_t=0.0,
              cand=0, clean=0, clean_same=0, clean_diff=0, dirty_same=0, dirty_diff=0,
              clean_t=0.0, cand_t=0.0, shut_first=0, dirty_bound=0, dirty_shut=0, dirty_both=0,
              bound_same=0, bound_same_t=0.0)
    cur = {}          # текущий вызов advance: трасса ступени 1 и её результат
    diffs = []        # чистые, но не совпавшие — опровержение

    o_adv, o_adv4 = m.advance, m.advance_fourth_stage
    o_phases, o_newton = m._advance_phases, m._newton_fixed_active_set
    o_trial, o_wf = m._trial_is_reasonable, m._well_fluxes

    def advance(state_old, dt_s, *a, **kw):
        cur.clear()
        cur.update(trace=True, newton=0, bound=0, shut=0, s1=None, seen2=False, failed=False,
                   in_advance=True)
        t0 = time.perf_counter()
        try:
            return o_adv(state_old, dt_s, *a, **kw)
        finally:
            dt = time.perf_counter() - t0
            st["advance"] += 1; st["advance_t"] += dt
            if cur.get("failed"):
                st["failed_adv_t"] += dt
            cur["trace"] = False; cur["in_advance"] = False

    def advance4(state_old, dt_s, *a, **kw):
        # Ступень 4 изнутри advance (self.advance_fourth_stage) — не «по памяти», учёт advance не трогать
        if cur.get("in_advance"):
            return o_adv4(state_old, dt_s, *a, **kw)
        cur.clear(); cur.update(trace=False)
        t0 = time.perf_counter()
        try:
            return o_adv4(state_old, dt_s, *a, **kw)
        finally:
            st["stage4_mem"] += 1; st["stage4_mem_t"] += time.perf_counter() - t0

    def phases(state_old, dt_s, *a, **kw):
        s = stage_of(m)
        t0 = time.perf_counter()
        new, rep = o_phases(state_old, dt_s, *a, **kw)
        dt = time.perf_counter() - t0
        if not cur.get("trace") and s == 1:
            return new, rep
        if s == 1:
            # конец трассы ступени 1: дальше счётчики не пишутся
            cur["trace"] = False
            cur["s1"] = (new.copy(), replace(rep))
            cur["failed"] = not rep.converged
            if not rep.converged:
                st["failed1"] += 1
        elif s == 2 and cur.get("s1") is not None and not cur["seen2"]:
            cur["seen2"] = True
            branch = m._well_branch or ""
            if branch == "shut":
                st["shut_first"] += 1          # останов: ступень 2 начинает с «закрыта» — не кандидат
            else:
                st["cand"] += 1; st["cand_t"] += dt
                s1n, s1r = cur["s1"]
                same = (all(np.array_equal(getattr(s1n, f), getattr(new, f)) for f in STATE_FIELDS)
                        and all(getattr(s1r, f) == getattr(rep, f) for f in REP_FIELDS))
                clean = cur["newton"] > 0 and cur["bound"] == 0 and cur["shut"] == 0
                if clean:
                    st["clean"] += 1; st["clean_t"] += dt
                    st["clean_same" if same else "clean_diff"] += 1
                    if not same:
                        diffs.append((s1r, replace(rep)))
                else:
                    st["dirty_same" if same else "dirty_diff"] += 1
                    # Верхняя оценка уточнённого признака (вариант 1в плана): нечистый только по
                    # границе, а итог всё равно побитово тот же
                    if same and cur["bound"] and not cur["shut"] and cur["newton"] > 0:
                        st["bound_same_t"] += dt; st["bound_same"] += 1
                    if cur["bound"] and cur["shut"]:
                        st["dirty_both"] += 1
                    elif cur["bound"]:
                        st["dirty_bound"] += 1
                    elif cur["shut"]:
                        st["dirty_shut"] += 1
        return new, rep

    def newton(*a, **kw):
        if cur.get("trace") and stage_of(m) == 1:
            cur["newton"] += 1
        return o_newton(*a, **kw)

    def trial(z, gas_active):
        ok = o_trial(z, gas_active)
        if not ok and cur.get("trace") and stage_of(m) == 1:
            # отвергла только граница: без неё точка принимается
            lo = m._sg_lower_bound
            m._sg_lower_bound = None
            try:
                if o_trial(z, gas_active):
                    cur["bound"] += 1
            finally:
                m._sg_lower_bound = lo
        return ok

    def wf(state):
        if (cur.get("trace") and m.control_mode == "BHP" and m._well_branch is None
                and float(state.pressure_bar[0]) <= float(m.p_bhp_bar)):
            cur["shut"] += 1
        return o_wf(state)

    m.advance, m.advance_fourth_stage = advance, advance4
    m._advance_phases, m._newton_fixed_active_set = phases, newton
    m._trial_is_reasonable, m._well_fluxes = trial, wf
    return st, diffs


# ── Сценарии ──

def _example(name):
    return lambda: load_config(SOLVER / "examples" / name / "config.json")


def _bug018():
    cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
    cfg.grid.N = 350
    return cfg


def _daily_shutin():
    # TestDailyShutin (tests/test_prototype_phase_switching.py): 10 сут добычи + 3 сут q_oil = 0
    cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
    hist = list(cfg.time.history)
    for _ in range(3):
        x = copy.deepcopy(hist[0])
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    return cfg


EXAMPLES = sorted(p.parent.name for p in (SOLVER / "examples").glob("*/config.json"))
SCENARIOS = {f"ex{n.split('_')[0]}": _example(n) for n in EXAMPLES}
SCENARIOS["bug018"] = _bug018
SCENARIOS["daily_shutin"] = _daily_shutin


def t04():
    """Первый шаг T04 прототипа (n = 100, p_wf = 100 бар, 60 с) — сценарий теста DEBT-030 и t04_attempts.py DEBT-069."""
    import importlib.util
    path = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "tests" / "helpers.py"
    spec = importlib.util.spec_from_file_location("proto_helpers", path)
    helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
    _, m, s = helpers.model_and_state(n=100, bhp=100.0, p0=200.0,
                                      case=helpers.ROOT / "regression" / "inputs" / "T04.xlsx")
    st, diffs = install(m)
    m.advance(s, 60.0)
    print(f"t04: отказов ступени 1 {st['failed1']}, кандидатов {st['cand']}, чистых {st['clean']} "
          f"(побитово {st['clean_same']}, НЕ побитово {st['clean_diff']}); нечистых {st['cand'] - st['clean']} "
          f"(граница {st['dirty_bound']}, «закрыта» {st['dirty_shut']}, обе {st['dirty_both']}): "
          f"побитово {st['dirty_same']}, не побитово {st['dirty_diff']}")


def run(name):
    if name == "t04":
        t04()
        return 0.0, dict.fromkeys(("clean_t", "failed_adv_t", "clean", "clean_same", "clean_diff", "cand",
                                   "failed1", "bound_same", "bound_same_t", "dirty_diff"), 0)
    cfg = SCENARIOS[name]()
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    m = sim._hydro._model
    st, diffs = install(m)
    t0 = time.perf_counter()
    err = ""
    try:
        sim.run(init)
    except Exception as exc:                     # отказ расчёта — тоже результат
        err = f"{type(exc).__name__}: {str(exc)[:120]}"
    total = time.perf_counter() - t0
    adv_t = st["advance_t"] + st["stage4_mem_t"]
    share = (lambda x: 100.0 * x / total if total > 0 else 0.0)
    print(f"{name}: {total:7.1f} с, advance {st['advance']} ({adv_t:.1f} с, {share(adv_t):.1f} %), "
          f"ступень 4 по памяти {st['stage4_mem']}; отказов ступени 1 {st['failed1']} "
          f"(advance с отказом {st['failed_adv_t']:.1f} с, {share(st['failed_adv_t']):.1f} %)")
    print(f"    ступень 2 начинает с «закрыта» {st['shut_first']}; кандидатов {st['cand']} ({st['cand_t']:.2f} с), "
          f"чистых {st['clean']} ({st['clean_t']:.2f} с, {share(st['clean_t']):.2f} % расчёта): "
          f"побитово {st['clean_same']}, НЕ побитово {st['clean_diff']}")
    print(f"    нечистых {st['cand'] - st['clean']} (граница {st['dirty_bound']}, «закрыта» {st['dirty_shut']}, "
          f"обе {st['dirty_both']}): побитово {st['dirty_same']}, не побитово {st['dirty_diff']}; "
          f"только граница и побитово {st['bound_same']} ({st['bound_same_t']:.2f} с, {share(st['bound_same_t']):.2f} %)"
          + (f"\n    РАСЧЁТ ОТКАЗАЛ: {err}" if err else ""))
    for r1, r2 in diffs:
        print(f"    !!! чистый, но разный: 1 = {[getattr(r1, f) for f in REP_FIELDS]}\n"
              f"                           2 = {[getattr(r2, f) for f in REP_FIELDS]}")
    sys.stdout.flush()
    return total, st


if __name__ == "__main__":
    print(f"Код: {_factory.__file__}")
    print(f"Прототип: {radial_blackoil.__file__}")
    names = sys.argv[1:] or list(SCENARIOS)
    keys = ("clean_t", "failed_adv_t", "clean", "clean_same", "clean_diff", "cand", "failed1",
            "bound_same", "bound_same_t", "dirty_diff")
    agg = dict(total=1e-12, **{k: 0 for k in keys})      # 1e-12: только t04 — без деления на 0
    for n in names:
        total, st = run(n)
        agg["total"] += total
        for k in keys:
            agg[k] += st[k]
    print(f"ИТОГО: расчёт {agg['total']:.1f} с; отказов ступени 1 {agg['failed1']}, кандидатов {agg['cand']}, "
          f"чистых {agg['clean']} (побитово {agg['clean_same']}, не побитово {agg['clean_diff']}); "
          f"время чистых кандидатов {agg['clean_t']:.1f} с = {100 * agg['clean_t'] / agg['total']:.2f} % расчёта, "
          f"{100 * agg['clean_t'] / max(agg['failed_adv_t'], 1e-12):.1f} % времени отказавших advance; "
          f"нечистые только по границе, но побитово: {agg['bound_same']} ({agg['bound_same_t']:.1f} с = "
          f"{100 * agg['bound_same_t'] / agg['total']:.2f} %); нечистые и разные {agg['dirty_diff']}")
