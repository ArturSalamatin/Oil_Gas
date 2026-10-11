"""DEBT-048: память ступени 4 в advance — замер на коде после DEBT-015 (локальное дробление G1a).

Код решателя не меняется: проба оборачивает методы экземпляра модели прототипа,
как vault/issues/debt-040/probes/stage_profile.py:
  _advance_phases — одно решение Ньютона (ступень — по флагам модели);
  advance         — шаг: какая ступень его решила (0 — отказ, дальше дробит Simulator).
Варианты (подменяются на экземпляре):
  0    — код базы;
  m1   — память: последний принятый шаг решила ступень 4 при том же управлении ->
         шаг начинается с неё; при её отказе — ступени 1-3 без её повтора.
         Отказ шага память не сбрасывает: повтор подшага h/2 тоже начинается с 4;
  m1r  — как m1, но любой отказ шага сбрасывает память (вариант 1 DEBT-040, install_v1);
  m2   — как m1, но память включается после 2 принятых подряд шагов ступени 4 (гистерезис);
  m2r  — M = 2, любой отказ шага сбрасывает память;
  m1s, m2s — «строгие» m1, m2: пока память включена, только ступень 4; её отказ — сразу
         отказ шага (Simulator делит подшаг пополам), без ступеней 1-3. После STRICT_F
         отказов ступени 4 подряд память сбрасывается — следующая попытка проходит все
         четыре ступени (страховка: шаг, который решили бы только ступени 1-3);
  m1rs, m2rs — строгие m1r, m2r: отказ ступени 4 — отказ шага и сброс памяти.

Режимы:
  e2e <конфиг> <n_prod> <n_shut> <A|B> <dt_integration> <вариант>
      как debt-040/probes/stage_profile.py: n_prod суточных интервалов добычи при p_wf
      примера, затем n_shut суток останова (A: p_wf = p_ext; B: q_oil = 0, min_bhp = 1 атм)
  examples <вариант> [имя ...]
      примеры (по умолчанию все): отпечаток истории, перепись ступеней, итерации Ньютона;
      при одном имени — ещё профиль по участкам «добыча» / «останов»
  table
      сводная таблица по строкам SUMMARY всех *.out.txt рядом со скриптом
  compare <имя> <вариант A> <вариант B>
      сравнение историй примера (hist_<имя>_<вариант>.npz пишет режим examples;
      .npz в git не идут): наибольшие отличия p, T, S_g, R_s, q_o и числа ячеек с газом

Вывод — в stdout и в файл рядом со скриптом (<режим>_<параметры>_<вариант>.out.txt, UTF-8):
перенаправление `>` в Windows PowerShell 5.1 пишет UTF-16 с искажённой кириллицей.

Допуск Ньютона (опыт к найденной проблеме R_s забойной ячейки, переменные окружения):
  DEBT048_GAS_SCALE — gas_residual_scale модели (по умолчанию max(R_s,ext, 1) = 300:
                      невязка газа делится на него, допуск по газу — 300 × atol м³ст/с);
  DEBT048_ATOL      — atol_sm3s Ньютона ступеней 1-4 (по умолчанию 1e-11 м³ст/с);
  DEBT048_TAG       — суффикс имён выходных файлов, чтобы не затереть основные замеры.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-048\\probes\\stage_memory.py e2e 20 10 3 B 3600 m1
    .venv\\Scripts\\python ..\\vault\\issues\\debt-048\\probes\\stage_memory.py examples m1
"""

import copy
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# DEBT048_SOLVER — numerical_solver проверяемого дерева; по умолчанию — основной каталог
SOLVER = Path(os.environ.get("DEBT048_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DAY = 86400.0
BAR = 1e5
BASES = {"20": "20_rs300_cooling", "19": "19_rs150_cooling", "21": "21_rs100_cooling"}
# вариант -> (M, сброс при отказе, строгий); STRICT_F — отказов ступени 4 подряд до сброса
VARIANTS = {"0": None, "m1": (1, False, False), "m1r": (1, True, False), "m2": (2, False, False),
            "m2r": (2, True, False), "m1s": (1, False, True), "m2s": (2, False, True),
            "m1rs": (1, True, True), "m2rs": (2, True, True)}
STRICT_F = 2
TAG = os.environ.get("DEBT048_TAG", "")
GAS_SCALE = os.environ.get("DEBT048_GAS_SCALE")
ATOL = os.environ.get("DEBT048_ATOL")


def apply_tolerance(model):
    """Подмена допуска Ньютона из окружения (опыт); без переменных — код базы."""
    if GAS_SCALE:
        model.gas_residual_scale = float(GAS_SCALE)
    if ATOL:
        # atol_sm3s — третий параметр по умолчанию у обоих Ньютонов прототипа:
        # _newton_fixed_active_set(..., max_iter=15, rtol=1e-8, atol_sm3s=1e-11) и
        # _newton_switching(..., max_iter=40, rtol=1e-8, atol_sm3s=1e-11, ...)
        cls = type(model)
        for name in ("_newton_fixed_active_set", "_newton_switching"):
            f = getattr(cls, name)
            d = list(f.__defaults__)
            d[2] = float(ATOL)
            f.__defaults__ = tuple(d)


class Tee:
    """Печать в stdout и в файл вывода."""

    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, *a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        self.f.write(line + "\n")
        self.f.flush()


def stage_of(m):
    """Ступень advance по флагам модели во время решения."""
    if m._phase_switching:
        return 4
    if m._line_search_l2:
        return 3
    if m._sg_lower_bound is None:
        return 2
    return 1


class Profile:
    """Журнал решений и шагов одной модели; period(m) — метка участка истории."""

    def __init__(self, model, period):
        self.m = model
        self.period = period
        self.solves = []    # (участок, ступень, ветка, с, сошлось, принято, итераций)
        self.steps = []     # (участок, ступень-решатель или 0, с, dt)
        base = model._advance_phases

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
            self.solves.append((self.period(m), st, br, sec, bool(rep.converged), ok,
                                int(rep.iterations)))
            return new, rep

        model._advance_phases = phases

    def wrap_advance(self):
        # advance_fourth_stage появляется с DEBT-048: на коде ветки адаптер вызывает его
        # по памяти мимо advance, и шаги по памяти без этой обёртки не попали бы в журнал
        for name in ("advance", "advance_fourth_stage"):
            if hasattr(self.m, name):
                setattr(self.m, name, self._step_logger(getattr(self.m, name)))

    def _step_logger(self, adv):
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

        return advance

    def summary(self, per):
        """Числа участка: вызовы, отказы, время, решения, итерации (всего и впустую)."""
        steps = [s for s in self.steps if s[0] == per]
        solves = [s for s in self.solves if s[0] == per]
        by = Counter(s[1] for s in steps)
        return {
            "calls": len(steps), "fail": by.get(0, 0),
            "stages": {str(k): by[k] for k in sorted(by)},
            "t_adv": round(sum(s[2] for s in steps), 2),
            "t_waste": round(sum(s[3] for s in solves if not s[5]), 2),
            "solves": len(solves),
            "iters": sum(s[6] for s in solves),
            "iters_waste": sum(s[6] for s in solves if not s[5]),
        }

    def report(self, out, per):
        steps = [s for s in self.steps if s[0] == per]
        solves = [s for s in self.solves if s[0] == per]
        if not steps:
            return
        sm = self.summary(per)
        out(f"  [{per}] вызовов advance {sm['calls']} (отказов {sm['fail']}), время advance "
            f"{sm['t_adv']:.1f} с; решила ступень: {sm['stages']} (0 — отказ)")
        out(f"    решений {sm['solves']}, итераций {sm['iters']}, из них впустую {sm['iters_waste']} "
            f"({100 * sm['iters_waste'] / max(sm['iters'], 1):.0f} %); впустую {sm['t_waste']:.1f} с = "
            f"{100 * sm['t_waste'] / max(sm['t_adv'], 1e-30):.0f} % времени advance")
        agg = defaultdict(lambda: [0, 0, 0, 0.0, 0.0, 0])   # решений, сошлось, принято, с, с впустую, итераций
        for _, st, br, sec, conv, ok, its in solves:
            a = agg[(st, br)]
            a[0] += 1; a[1] += conv; a[2] += ok; a[3] += sec; a[5] += its
            if not ok:
                a[4] += sec
        out("    ступень ветка   | решений | сошлось | принято |  время, с | впустую, с | итераций | ср.")
        for (st, br) in sorted(agg, key=lambda k: (k[0], str(k[1]))):
            a = agg[(st, br)]
            out(f"    {st:>7} {str(br or '-'):<7} | {a[0]:>7} | {a[1]:>7} | {a[2]:>7} | {a[3]:>9.1f} | "
                f"{a[4]:>10.1f} | {a[5]:>8} | {a[5] / max(a[0], 1):>4.1f}")
        # Серии принятых шагов, решённых ступенью 4 подряд (отказы пропускаются: память m1
        # и m2 отказ не сбрасывает). В серии длины L память M=1 могла бы начать со ступени 4
        # L-1 шагов, M=2 — L-2: разница M=1 и M=2 — около числа серий длины >= 2.
        acc = [s[1] for s in steps if s[1] != 0]
        runs, L = [], 0
        for st in acc + [None]:
            if st == 4:
                L += 1
            elif L:
                runs.append(L); L = 0
        if runs:
            hist = Counter(min(r, 11) for r in runs)
            out(f"    серии шагов ступени 4: {len(runs)}, шагов в них {sum(runs)}; "
                f"покрыла бы память M=1 {sum(r - 1 for r in runs)}, M=2 {sum(max(r - 2, 0) for r in runs)}; "
                f"длины (11 = 11 и больше): {dict(sorted(hist.items()))}")


MEM = Counter()


def install_memory(model, M, reset_on_failure, strict):
    """Память ступени 4: после M принятых подряд шагов ступени 4 при том же управлении шаг начинается с неё."""
    base = model.advance            # метод класса: ступени 1-4 по порядку
    # управление, число принятых подряд шагов ступени 4, отказов ступени 4 подряд (строгий)
    mem = {"key": None, "run": 0, "fails": 0}

    def key_of(m):
        return (m.control_mode, m.p_bhp_bar, m.oil_rate_target_sm3_day, m.min_bhp_bar)

    def advance(state_old, dt_s, max_active_iter=12, max_newton=15):
        m = model
        key = key_of(m)
        if key != mem["key"]:
            mem.update(key=key, run=0, fails=0)      # смена управления — память с нуля
        if mem["run"] >= M:
            MEM["first4"] += 1
            m._phase_switching = True
            try:
                new, rep = m._fallback(state_old, dt_s, max_active_iter, max_newton)
                rep.globalized = True; rep.phase_switching = True
            finally:
                m._phase_switching = False
            if rep.converged:
                MEM["first4_ok"] += 1
                mem["run"] += 1
                mem["fails"] = 0
                return new, rep
            if strict:
                # отказ шага без ступеней 1-3; сброс памяти — сразу (r) или после
                # STRICT_F отказов подряд
                mem["fails"] += 1
                if reset_on_failure or mem["fails"] >= STRICT_F:
                    MEM["dropped"] += 1
                    mem.update(run=0, fails=0)
                return new, rep
            # ступень 4 отказала: ступени 1-3 без её повтора
            m.phase_switching_stage = False
            try:
                new, rep = base(state_old, dt_s, max_active_iter, max_newton)
            finally:
                m.phase_switching_stage = True
            if rep.converged:
                MEM["rescued"] += 1
                mem["run"] = 0                   # шаг решила ступень 1-3
            elif reset_on_failure:
                mem["run"] = 0
            return new, rep
        new, rep = base(state_old, dt_s, max_active_iter, max_newton)
        if rep.converged:
            mem["run"] = mem["run"] + 1 if rep.phase_switching else 0
            mem["fails"] = 0
        elif reset_on_failure:
            mem["run"] = 0
        return new, rep

    model.advance = advance


def install(model, variant):
    spec = VARIANTS[variant]
    if spec is not None:
        install_memory(model, *spec)


def code_paths():
    """Каталоги пакетов, которые реально импортированы (проверка дерева)."""
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


def shut_period(m):
    """Участок примера: останов — управление по дебиту нефти с нулевым дебитом."""
    shut = m.control_mode == "OIL_RATE" and float(m.oil_rate_target_sm3_day) == 0.0
    return "останов" if shut else "добыча"


def run_e2e(args):
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    base_key, n_prod, n_shut, mode, dt_int, variant = args
    n_prod, n_shut, dt_int = int(n_prod), int(n_shut), float(dt_int)
    out = Tee(HERE / f"e2e_{base_key}{mode}_{dt_int:.0f}_{variant}{TAG}.out.txt")
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
    # Опыт аудита (2026-10-10): глубина дробления и условие сходимости по ячейке (BUG-022)
    # из окружения; DEBT048_CELL_TOL=none — условие выключено (cell_tol = None у прототипа)
    if os.environ.get("DEBT048_MAX_RETRIES"):
        cfg.numerics.max_retries = int(os.environ["DEBT048_MAX_RETRIES"])
    if os.environ.get("DEBT048_CELL_TOL"):
        v = os.environ["DEBT048_CELL_TOL"]
        cfg.numerics.newton_cell_tol = None if v == "none" else float(v)
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    assert model.phase_switching_stage is True
    apply_tolerance(model)
    p_ext_bar = p_ext / BAR

    def period(m):
        shut = (m.control_mode == "OIL_RATE") if mode == "B" else \
            (m.control_mode == "BHP" and abs(m.p_bhp_bar - p_ext_bar) < 1e-6)
        return "останов" if shut else "добыча"

    prof = Profile(model, period)
    install(model, variant)
    prof.wrap_advance()
    out(code_paths())
    out(f"=== {BASES[base_key]}: {n_prod} сут добычи + {n_shut} сут останова ({mode}); "
        f"вариант {variant}; dt_integration = {dt_int:.0f} с, max_retries = {cfg.numerics.max_retries}, "
        f"newton_cell_tol = {getattr(cfg.numerics, 'newton_cell_tol', '—')} ===")
    t0 = time.perf_counter()
    try:
        h = sim.run(init)
        fp, ok = fingerprint(h), True
        status = f"✓ отпечаток {fp}"
        save_history(h, HERE / f"hist_e2e_{base_key}{mode}_{dt_int:.0f}_{variant}{TAG}.npz")
    except RuntimeError as e:
        fp, ok = None, False
        status = f"✗ {str(e)[:200]}"
    wall = time.perf_counter() - t0
    out(f"итог: {status}; счёт {wall:.0f} с")
    for per in ("добыча", "останов"):
        prof.report(out, per)
    if MEM:
        out(f"  память: начато со ступени 4 {MEM['first4']}, из них сошлось {MEM['first4_ok']}; "
            f"после её отказа шаг решили ступени 1-3 {MEM['rescued']}; сбросов строгого {MEM['dropped']}")
    out("SUMMARY " + json.dumps({
        "case": f"{base_key}{mode} {dt_int:.0f}{TAG}", "variant": variant, "ok": ok, "fp": fp,
        "wall": round(wall, 1), "shut": prof.summary("останов"), "prod": prof.summary("добыча"),
        "mem": dict(MEM)}, ensure_ascii=False))


def run_examples(args):
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    variant = args[0]
    names = args[1:] or sorted(p.parent.name for p in (SOLVER / "examples").glob("*/config.json"))
    tag = names[0] if len(names) == 1 else "all"
    out = Tee(HERE / f"examples_{tag}_{variant}{TAG}.out.txt")
    out(code_paths())
    if GAS_SCALE or ATOL:
        out(f"    допуск: gas_residual_scale = {GAS_SCALE or 'по умолчанию'}, atol_sm3s = {ATOL or '1e-11'}")
    for name in names:
        MEM.clear()
        cfg = load_config(SOLVER / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        apply_tolerance(model)
        prof = Profile(model, shut_period)
        install(model, variant)
        prof.wrap_advance()
        t0 = time.perf_counter()
        try:
            hist = sim.run(init)
            fp, ok = fingerprint(hist), True
            save_history(hist, HERE / f"hist_{name}_{variant}{TAG}.npz")
        except RuntimeError as e:
            fp, ok = f"✗ {str(e)[:80]}", False
        wall = time.perf_counter() - t0
        by = Counter(s[1] for s in prof.steps)
        iters = sum(s[6] for s in prof.solves)
        out(f"{name:<28} {wall:6.1f} с  отпечаток {fp}  ступени {dict(sorted(by.items()))}  "
            f"итераций {iters}  память {dict(MEM)}")
        if len(names) == 1:
            for per in ("добыча", "останов"):
                prof.report(out, per)
            out("SUMMARY " + json.dumps({
                "case": f"{name}{TAG}", "variant": variant, "ok": ok, "fp": fp, "wall": round(wall, 1),
                "shut": prof.summary("останов"), "prod": prof.summary("добыча"), "mem": dict(MEM)},
                ensure_ascii=False))


def save_history(history, path):
    """Записи истории в .npz: p, T, S_g, R_s (запись × ячейка), времена, q_o."""
    np.savez(path,
             p=np.array([s.p for s in history.states]), T=np.array([s.T for s in history.states]),
             Sg=np.array([s.Sg for s in history.states]), Rs=np.array([s.Rs for s in history.states]),
             t=np.asarray(history.times, float),
             q_o=np.array([w.q_o_std for w in history.well_data], float))


def run_compare(args):
    name, va, vb = args
    a = np.load(HERE / f"hist_{name}_{va}.npz")
    b = np.load(HERE / f"hist_{name}_{vb}.npz")
    out = Tee(HERE / f"compare_{name}_{va}_{vb}.out.txt")
    out(f"=== {name}: {va} против {vb}; записей {len(a['t'])} / {len(b['t'])} ===")
    if a["p"].shape != b["p"].shape:
        out("  разные размеры историй — сравнение невозможно")
        return
    for key, unit, scale in (("p", "бар", BAR), ("T", "К", 1.0), ("Sg", "", 1.0), ("Rs", "м³/м³", 1.0)):
        d = np.abs(a[key] - b[key]) / scale
        n, j = np.unravel_index(int(np.argmax(d)), d.shape)
        out(f"  {key}: max|Δ| = {d.max():.3e} {unit} (запись {n}, ячейка {j}); "
            f"у забоя max|Δ| = {d[:, 0].max():.3e}; побитово записей {int(np.sum(np.all(d == 0, axis=1)))}")
    dq = np.abs(a["q_o"] - b["q_o"])
    out(f"  q_o: max|Δ| = {dq.max():.3e} м³ст/с")
    ga = np.count_nonzero(a["Sg"] > 0, axis=1)
    gb = np.count_nonzero(b["Sg"] > 0, axis=1)
    diff = [(int(n), int(ga[n]), int(gb[n])) for n in np.flatnonzero(ga != gb)]
    out(f"  ячеек с газом: различаются на записях {diff if diff else 'нигде'}")
    out(f"  T(r_w) последней записи: {a['T'][-1, 0]:.6f} / {b['T'][-1, 0]:.6f} К; "
        f"p(r_w): {a['p'][-1, 0] / BAR:.6f} / {b['p'][-1, 0] / BAR:.6f} бар")


def run_fptable(_args):
    """Отпечатки примеров по вариантам: «=» — побитово как вариант 0; иначе ступени варианта."""
    import re
    pat = re.compile(r"^(\S+)\s+([\d.]+) с\s+отпечаток (\S+)\s+ступени (\{[^}]*\})\s+итераций (\d+)")
    runs = {}
    for v in VARIANTS:
        f = HERE / f"examples_all_{v}{TAG}.out.txt"
        if f.exists():
            runs[v] = {m.group(1): (m.group(3), m.group(4), int(m.group(5)))
                       for m in map(pat.match, f.read_text(encoding="utf-8").splitlines()) if m}
    base = runs["0"]
    out = Tee(HERE / f"fptable{TAG}.out.txt")
    out("| пример | ступени (0) | итераций (0) | " + " | ".join(v for v in runs if v != "0") + " |")
    out("|---|---|---|" + "---|" * (len(runs) - 1))
    for name, (fp0, st0, it0) in base.items():
        cells = []
        for v, r in runs.items():
            if v == "0":
                continue
            fp, st, it = r[name]
            cells.append("=" if fp == fp0 else f"≠ {st}, итераций {it}")
        out(f"| {name} | {st0} | {it0} | " + " | ".join(cells) + " |")


def run_table(_args):
    rows = []
    for f in sorted(HERE.glob("*.out.txt")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("SUMMARY "):
                rows.append(json.loads(line[8:]))
    order = {v: i for i, v in enumerate(VARIANTS)}
    rows.sort(key=lambda r: (r["case"], order.get(r["variant"], 99)))
    print("| сценарий | вариант | итог | счёт, с | останов: advance (отказов) | время advance, с | "
          "впустую, с | итераций (впустую) | ступень 4 первой (сошлось / спасли 1-3) | отпечаток |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        s, mm = r["shut"], r["mem"]
        mem = (f"{mm.get('first4', 0)} ({mm.get('first4_ok', 0)} / {mm.get('rescued', 0)}"
               f"{', сбросов ' + str(mm['dropped']) if mm.get('dropped') else ''})" if mm else "—")
        print(f"| {r['case']} | {r['variant']} | {'✓' if r['ok'] else '✗'} | {r['wall']:.0f} | "
              f"{s['calls']} ({s['fail']}) | {s['t_adv']:.1f} | {s['t_waste']:.1f} | "
              f"{s['iters']} ({s['iters_waste']}) | {mem} | `{r['fp']}` |")


if __name__ == "__main__":
    {"e2e": run_e2e, "examples": run_examples, "table": run_table,
     "compare": run_compare, "fptable": run_fptable}[sys.argv[1]](sys.argv[2:])
