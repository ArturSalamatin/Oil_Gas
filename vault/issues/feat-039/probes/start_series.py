"""FEAT-039 (планирование): нарастающий шаг на первом интервале – пуск скважины из равновесия.

Пакет не правится: подменяется first_substep_depth экземпляра расписания.

Режимы (из numerical_solver/, P – путь к скрипту):
    .venv\\Scripts\\python P start <имя> <h0|none> ...
        только первый интервал истории считается сменой управления: его первый
        шаг – от подшага dt/2**m <= h0 с удвоением; интервалы k > 0 – как в
        конфиге (у 16, 17 – поле 0.11 с, у остальных нарастания нет). none –
        штатный прогон (первый интервал полным шагом)
    .venv\\Scripts\\python P all <имя> <h0|none> ...
        поведение после FEAT-039 при поле time.dt_after_control_change = h0:
        нарастание на первом интервале и на всех сменах управления; none –
        поле null (нарастания нет нигде)
    .venv\\Scripts\\python P octave <имя> <F> <j> ...
        первый интервал истории (длина D, первая запись) заменён шагами:
        первый D/2**F при любом j; ступени D/2**(F-j), D/2**(F-j), ...,
        D/2, каждая поделена на 2**j равных шагов («2**j шагов на октаву»,
        как octave в bug-026/probes/h0_series.py). j = 0 – нарастание с
        h0 = D/2**F; j -> бесконечность – предел равномерного сгущения
В каждом режиме первый прогон – база: остальные сравниваются с ним по
забойной ячейке; в конце – разности соседних прогонов и оценка Ричардсона
при q = 1 по первой записи (соседние h0 или j должны отличаться вдвое).
"""

import copy
import hashlib
import sys
import time
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

DAY, BAR = 86400.0, 1e5


def parse_h0(a):
    return None if a == "none" else float(a)


def config_path(name):
    """Конфиг примера; у 22 – перевод книги из output/input/ (FEAT-036)."""
    p = SOLVER_ROOT / "examples" / name / "config.json"
    return p if p.exists() else SOLVER_ROOT / "examples" / name / "output" / "input" / "config.json"


def depth_for(dt, h0):
    """Наименьшее m >= 0, при котором dt/2**m <= h0 (как TimeSchedule.first_substep_depth)."""
    m = 0
    while dt / 2 ** m > h0:
        m += 1
    return m


def patch_first(sim, h0):
    """Интервал 0 – смена управления с первым подшагом <= h0; k > 0 – штатно."""
    sched = sim._schedule
    orig = type(sched).first_substep_depth

    def depth(k):
        if k > 0:
            return orig(sched, k)
        _, dt = sched.substeps(0)
        return depth_for(dt, h0)

    sched.first_substep_depth = depth


def fingerprint(hist):
    """Отпечаток истории: sha256 полей p, Sg, Rs, T всех записей."""
    hsh = hashlib.sha256()
    for st in hist.states:
        for f in ("p", "Sg", "Rs", "T"):
            hsh.update(np.ascontiguousarray(getattr(st, f), dtype=float).tobytes())
    return hsh.hexdigest()[:16]


def run(cfg, label, h0_first=None, t_first=None):
    """Прогон: подшаги и отказы гидродинамики (всего и до первой записи), счёт, первая запись."""
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    if h0_first is not None:
        patch_first(sim, h0_first)
    D = sim._schedule.intervals[0].dt if t_first is None else t_first
    st = {"ok": 0, "fail": 0, "ok1": 0, "fail1": 0, "first": None}
    solve = sim._hydro.solve

    # Обёртка: считает принятые и отказавшие подшаги; отказ (HydroConvergenceError)
    # запускает дробление DEBT-015 – шаги перестают быть заданными нарастанием.
    def counting(state, dt, bc):
        before = state.t < D - 1e-9
        try:
            res = solve(state, dt, bc)
        except HydroConvergenceError:
            st["fail"] += 1
            st["fail1"] += before
            raise
        st["ok"] += 1
        st["ok1"] += before
        if st["first"] is None:
            st["first"] = dt
        return res

    sim._hydro.solve = counting
    t0 = time.perf_counter()
    try:
        hist = sim.run(s0)
    except RuntimeError as exc:
        print(f"{label}: ОТКАЗ – {exc}".splitlines()[0], flush=True)
        return None
    wall = time.perf_counter() - t0
    times = np.array(hist.times)
    i1 = int(np.argmin(np.abs(times - D)))
    assert abs(times[i1] - D) < 1e-6, (times[i1], D)
    r = hist.states[i1]
    print(f"{label}: первый подшаг {st['first']:.4g} с; до первой записи (t = {D:g} с) "
          f"принято {st['ok1']}, отказов {st['fail1']}; всего {st['ok']} / {st['fail']}; "
          f"счёт {wall:.1f} с; отпечаток {fingerprint(hist)}", flush=True)
    print(f"    первая запись: T(r_w) {r.T[0]:.4f} К, R_s(r_w) {r.Rs[0]:.4f}, "
          f"S_g(r_w) {r.Sg[0]:.5f}, p(r_w) {r.p[0] / BAR:.4f} бар", flush=True)
    return {"hist": hist, "i1": i1, "rec": r, "wall": wall, "ok": st["ok"]}


def compare(base, other, label):
    """Отличие other от base по забойной ячейке на общих моментах записи."""
    tb, to = np.array(base["hist"].times), np.array(other["hist"].times)
    common = np.intersect1d(np.round(tb, 6), np.round(to, 6))
    ib = np.searchsorted(np.round(tb, 6), common)
    io = np.searchsorted(np.round(to, 6), common)
    out = []
    for f, sc, unit in (("T", 1.0, "К"), ("Rs", 1.0, ""), ("p", 1 / BAR, "бар")):
        a = np.array([getattr(base["hist"].states[i], f)[0] for i in ib]) * sc
        b = np.array([getattr(other["hist"].states[i], f)[0] for i in io]) * sc
        k = int(np.argmax(np.abs(b - a)))
        out.append(f"max|Δ{f}(r_w)| {abs(b[k] - a[k]):.4f} {unit} (t = {common[k] / DAY:.4f} сут)")
    Tb = base["hist"].states[-1].T[0]
    To = other["hist"].states[-1].T[0]
    print(f"  {label} против базы: " + "; ".join(out) + f"; на конце ΔT {To - Tb:+.4f} К; "
          f"счёт ×{other['wall'] / base['wall']:.2f}, подшагов {other['ok']} против {base['ok']}",
          flush=True)


def series(results):
    """Разности соседних прогонов по первой записи и Ричардсон при q = 1."""
    keys = [k for k, v in results.items() if v is not None]
    for (k1, k2) in zip(keys, keys[1:]):
        a, b = results[k1]["rec"], results[k2]["rec"]
        print(f"  {k1} -> {k2}: ΔT(r_w) {b.T[0] - a.T[0]:+.5f} К, Ричардсон T {2 * b.T[0] - a.T[0]:.5f}; "
              f"ΔR_s(r_w) {b.Rs[0] - a.Rs[0]:+.4f}, Ричардсон R_s {2 * b.Rs[0] - a.Rs[0]:.4f}; "
              f"Δp(r_w) {(b.p[0] - a.p[0]) / BAR:+.5f} бар", flush=True)


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    mode, name = sys.argv[1], sys.argv[2]
    results = {}
    if mode in ("start", "all"):
        for a in sys.argv[3:]:
            cfg = load_config(config_path(name))
            h0 = parse_h0(a)
            if mode == "all":
                cfg.time.dt_after_control_change = h0
            label = f"{name} {mode} h0={a}"
            results[f"h0={a}"] = run(cfg, label, h0_first=h0)
    elif mode == "octave":
        F = int(sys.argv[3])
        for a in sys.argv[4:]:
            j = int(a)
            M = F - j
            cfg = load_config(config_path(name))
            hist = cfg.time.history
            D = hist[0].dt
            assert cfg.time.dt_integration >= D / 2, "шаги D/2 не помещаются в один шаг"
            base = [D / 2 ** M] + [D / 2 ** i for i in range(M, 0, -1)]
            assert abs(sum(base) - D) < 1e-9 * D
            tail = []
            for H in base:
                for _ in range(2 ** j):
                    x = copy.deepcopy(hist[0])
                    x.dt = H / 2 ** j
                    tail.append(x)
            cfg.time.history = tail + list(hist[1:])
            label = f"{name} octave F={F} (первый {D / 2 ** F:.4g} с), j={j}, шагов {len(tail)}"
            results[f"j={j}"] = run(cfg, label, t_first=D)
    else:
        raise SystemExit(f"неизвестный режим {mode}")
    keys = [k for k, v in results.items() if v is not None]
    if keys:
        b = results[keys[0]]
        for k in keys[1:]:
            compare(b, results[k], k)
    series(results)


if __name__ == "__main__":
    main()
