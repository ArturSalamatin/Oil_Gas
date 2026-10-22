"""DEBT-040: профиль ступеней advance — время и исходы решений по ступеням и веткам скважины.

Код решателя не меняется: проба оборачивает методы экземпляра модели прототипа.
  _advance_phases — одно решение (ступень по флагам модели, ветка — _well_branch);
  advance         — шаг (какая ступень его решила).
Варианты DEBT-040 подменяются на экземпляре:
  0   — код базы;
  v1  — помнить ступень 4: шаг после решённого ступенью 4 (при том же управлении
        скважиной) начинается с неё; при её отказе — ступени 1-3 без повтора ступени 4;
  v2  — при BHP не пробовать ветку «открыта», если p_ext <= p_wf и max p_old <= p_wf;
  v12 — оба.

Режимы:
  e2e <конфиг> <n_prod> <n_shut> <A|B> <dt_integration> <вариант>
      n_prod суточных интервалов добычи при p_wf примера, затем n_shut суток останова
      (A: p_wf = p_ext; B: q_oil = 0, min_bhp = 1 атм) — как bug-020/probes/e2e_shutin.py
  examples <вариант> [имя ...]
      примеры (по умолчанию все 21): перепись ветки «открыта», отпечатки истории
      (sha256 p, T, S_g, R_s всех записей и q_o) для побитовой сверки вариантов

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-040\\probes\\stage_profile.py e2e 20 10 3 A 3600 0
    .venv\\Scripts\\python ..\\vault\\issues\\debt-040\\probes\\stage_profile.py examples 0
"""

import copy
import hashlib
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# DEBT040_SOLVER — numerical_solver проверяемого дерева; по умолчанию — основной каталог
SOLVER = Path(os.environ.get("DEBT040_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.blackoil import RadialBlackOilModel  # noqa: E402

DAY = 86400.0
BAR = 1e5
BASES = {"20": "20_rs300_cooling", "19": "19_rs150_cooling",
         "21": "21_rs100_cooling", "14": "14_high_gor_cooling"}
ALL_EXAMPLES = [
    "01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey", "04_table_table",
    "04a_high_gas_saturation", "05_standing_table_rp", "06_table_corey_rp",
    "07_degassing_adiabatic_only", "08_degassing_jt", "09_degassing_latent_heat",
    "10_deep_degassing", "11_degassing_at_boundary", "12_large_drainage_radius",
    "13a_pwf_ramp_down", "13b_pwf_alternating", "14_high_gor_cooling", "15_oil_rate_ramp_up",
    "16_well_shut_in", "19_rs150_cooling", "20_rs300_cooling", "21_rs100_cooling",
]


def stage_of(m):
    """Ступень advance по флагам модели во время решения."""
    if m._phase_switching:
        return 4
    if m._line_search_l2:
        return 3
    if m._sg_lower_bound is None:
        return 2
    return 1


def open_is_hopeless(m, state_old):
    """Условие варианта 2: ветка «открыта» не может быть согласована (принцип максимума)."""
    target = float(m.p_bhp_bar)
    return m.p_outer_bar <= target and float(np.max(state_old.pressure_bar)) <= target


class Profile:
    """Журнал решений и шагов одной модели; period(m) — метка участка истории."""

    def __init__(self, model, period):
        self.m = model
        self.period = period
        self.solves = []    # (участок, ступень, ветка, с, сошлось, принято, итераций)
        self.steps = []     # (участок, ступень-решатель или 0, с, dt)
        self.census = Counter()   # (условие варианта 2, принято) для попыток ветки «открыта»
        base = model._advance_phases   # связанный метод класса (вариантов здесь нет)

        def phases(state_old, dt_s, max_active_iter=12, max_newton=15):
            m = self.m
            st, br = stage_of(m), m._well_branch
            t0 = time.perf_counter()
            new, rep = base(state_old, dt_s, max_active_iter, max_newton)
            sec = time.perf_counter() - t0
            ok = bool(rep.converged)
            if ok and br is not None:
                # _fallback принимает только согласованную ветку (blackoil.py, _fallback)
                p0, target = float(new.pressure_bar[0]), float(m.p_bhp_bar)
                ok = p0 >= target if br == "open" else p0 <= target
            if m.control_mode == "BHP" and br == "open":
                self.census[(open_is_hopeless(m, state_old), ok)] += 1
            self.solves.append((self.period(m), st, br, sec, bool(rep.converged), ok, rep.iterations))
            return new, rep

        model._advance_phases = phases

    def wrap_advance(self):
        adv = self.m.advance

        def advance(state_old, dt_s, *a, **kw):
            per = self.period(self.m)
            t0 = time.perf_counter()
            new, rep = adv(state_old, dt_s, *a, **kw)
            sec = time.perf_counter() - t0
            st = 0
            if rep.converged:
                st = 4 if rep.phase_switching else 3 if rep.globalized else 2 if rep.fallback else 1
            self.steps.append((per, st, sec, dt_s))
            return new, rep

        self.m.advance = advance

    def report(self, per):
        steps = [s for s in self.steps if s[0] == per]
        solves = [s for s in self.solves if s[0] == per]
        if not steps:
            return
        t_adv = sum(s[2] for s in steps)
        by = Counter(s[1] for s in steps)
        print(f"  [{per}] вызовов advance {len(steps)}, время advance {t_adv:.1f} с; "
              f"решила ступень: " + ", ".join(f"{k}: {by[k]}" for k in sorted(by)) + " (0 — отказ)")
        agg = defaultdict(lambda: [0, 0, 0, 0.0, 0.0, 0])   # вызовов, сошлось, принято, с, с впустую, итераций
        for _, st, br, sec, conv, ok, its in solves:
            a = agg[(st, br)]
            a[0] += 1; a[1] += conv; a[2] += ok; a[3] += sec; a[5] += its
            if not ok:
                a[4] += sec
        waste = sum(a[4] for a in agg.values())
        print(f"    решений {len(solves)}; впустую (не принято) {waste:.1f} с = {100 * waste / max(t_adv, 1e-30):.0f} % времени advance")
        print("    ступень ветка   | решений | сошлось | принято |  время, с | впустую, с | итераций ср.")
        for (st, br) in sorted(agg, key=lambda k: (k[0], str(k[1]))):
            a = agg[(st, br)]
            print(f"    {st:>7} {str(br or '-'):<7} | {a[0]:>7} | {a[1]:>7} | {a[2]:>7} | {a[3]:>9.1f} | {a[4]:>10.1f} | {a[5] / max(a[0], 1):>6.1f}")


def install_v2(model):
    """Вариант 2: копия RadialBlackOilModel._fallback, ветка «открыта» пропускается при open_is_hopeless."""
    def fallback(state_old, dt_s, max_active_iter, max_newton):
        self = model
        self._sg_lower_bound = None
        try:
            if self.control_mode != 'BHP':
                new, rep = self._advance_phases(state_old, dt_s, max_active_iter, max_newton)
                rep.fallback = True
                return new, rep
            target = float(self.p_bhp_bar)
            branch = 'shut' if float(state_old.pressure_bar[0]) <= target else 'open'
            tried = []
            while True:
                tried.append(branch); self._well_branch = branch
                new, rep = self._advance_phases(state_old, dt_s, max_active_iter, max_newton)
                rep.fallback = True; rep.well_branch = branch; rep.well_switches = len(tried) - 1
                if rep.converged:
                    p0 = float(new.pressure_bar[0])
                    if (p0 >= target) if branch == 'open' else (p0 <= target):
                        return new, rep
                other = 'open' if branch == 'shut' else 'shut'
                # DEBT-040, вариант 2
                if other in tried or (other == 'open' and open_is_hopeless(self, state_old)):
                    rep.converged = False
                    return new, rep
                branch = other
        finally:
            self._sg_lower_bound = -0.05; self._well_branch = None
    model._fallback = fallback


V1_STATS = Counter()


def install_v1(model):
    """Вариант 1: после шага, решённого ступенью 4, следующий шаг (то же управление) — сразу с неё."""
    base = model.advance
    mem = {"key": None}

    def key_of(m):
        return (m.control_mode, m.p_bhp_bar, m.oil_rate_target_sm3_day, m.min_bhp_bar)

    def advance(state_old, dt_s, max_active_iter=12, max_newton=15):
        m = model
        key = key_of(m)
        if mem["key"] is not None and mem["key"] == key:
            V1_STATS["first4"] += 1
            m._phase_switching = True
            try:
                new, rep = m._fallback(state_old, dt_s, max_active_iter, max_newton)
                rep.globalized = True; rep.phase_switching = True
            finally:
                m._phase_switching = False
            if rep.converged:
                V1_STATS["first4_ok"] += 1
                return new, rep
            # ступень 4 отказала: ступени 1-3 без её повтора, память сброшена
            mem["key"] = None
            m.phase_switching_stage = False
            try:
                return base(state_old, dt_s, max_active_iter, max_newton)
            finally:
                m.phase_switching_stage = True
        new, rep = base(state_old, dt_s, max_active_iter, max_newton)
        mem["key"] = key if (rep.converged and rep.phase_switching) else None
        return new, rep
    model.advance = advance


def install(model, variant):
    if "2" in variant:
        install_v2(model)
    if "1" in variant:
        install_v1(model)


def code_paths():
    """Каталоги пакетов, которые реально импортированы (проверка дерева в worktree)."""
    import gpn_multiphase_solver
    import radial_blackoil
    return f"    код: {Path(gpn_multiphase_solver.__file__).parent}, {Path(radial_blackoil.__file__).parent}"


def fingerprint(history):
    """sha256 истории: p, T, S_g, R_s всех записей, времена и q_o — для побитовой сверки."""
    h = hashlib.sha256()
    for s in history.states:
        for a in (s.p, s.T, s.Sg, s.Rs):
            h.update(np.ascontiguousarray(a, dtype=float).tobytes())
    h.update(np.asarray(history.times, float).tobytes())
    h.update(np.asarray([w.q_o_std for w in history.well_data], float).tobytes())
    return h.hexdigest()[:16]


def run_e2e(args):
    base_key, n_prod, n_shut, mode, dt_int, variant = args
    n_prod, n_shut, dt_int = int(n_prod), int(n_shut), float(dt_int)
    cfg = load_config(SOLVER / "examples" / BASES[base_key] / "config.json")
    cfg.output.log_level = "ERROR"
    iv = cfg.time.history[0]
    p_ext = cfg.initial_conditions.p0
    hist = []
    for _ in range(n_prod):
        x = copy.deepcopy(iv); x.dt = DAY; hist.append(x)
    for _ in range(n_shut):
        x = copy.deepcopy(iv); x.dt = DAY
        if mode == "A":
            x.control, x.p_wf = "pressure", p_ext
        else:
            x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    cfg.time.dt_integration = dt_int
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    assert model.phase_switching_stage is True
    p_ext_bar = p_ext / BAR

    def period(m):
        shut = (m.control_mode == "OIL_RATE") if mode == "B" else \
            (m.control_mode == "BHP" and abs(m.p_bhp_bar - p_ext_bar) < 1e-6)
        return "останов" if shut else "добыча"

    prof = Profile(model, period)
    install(model, variant)
    prof.wrap_advance()
    print(code_paths())
    print(f"=== {BASES[base_key]}: {n_prod} сут добычи + {n_shut} сут останова ({mode}); "
          f"вариант {variant}; dt_integration = {dt_int:.0f} с, max_retries = {cfg.numerics.max_retries} ===")
    t0 = time.perf_counter()
    try:
        h = sim.run(init)
        status = f"✓ отпечаток {fingerprint(h)}"
    except RuntimeError as e:
        status = f"✗ {str(e)[:160]}"
    print(f"итог: {status}; счёт {time.perf_counter() - t0:.0f} с")
    for per in ("добыча", "останов"):
        prof.report(per)
    print(f"  перепись «открыта» (условие варианта 2, принято): {dict(prof.census)}")
    if V1_STATS:
        print(f"  вариант 1: начато со ступени 4 {V1_STATS['first4']}, из них сошлось {V1_STATS['first4_ok']}")


def run_examples(args):
    variant, names = args[0], (args[1:] or ALL_EXAMPLES)
    total = Counter()
    print(code_paths(), flush=True)
    for name in names:
        cfg = load_config(SOLVER / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        prof = Profile(model, lambda m: "все")
        install(model, variant)
        prof.wrap_advance()
        t0 = time.perf_counter()
        try:
            fp = fingerprint(sim.run(init))
        except RuntimeError as e:
            fp = f"✗ {str(e)[:80]}"
        by = Counter(s[1] for s in prof.steps)
        total.update(prof.census)
        print(f"{name:<28} {time.perf_counter() - t0:6.1f} с  отпечаток {fp}  "
              f"ступени {dict(sorted(by.items()))}  «открыта» {dict(prof.census)}", flush=True)
    print(f"перепись «открыта» по всем (условие варианта 2, принято): {dict(total)}")


if __name__ == "__main__":
    {"e2e": run_e2e, "examples": run_examples}[sys.argv[1]](sys.argv[2:])
