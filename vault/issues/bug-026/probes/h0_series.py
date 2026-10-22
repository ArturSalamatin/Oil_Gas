"""BUG-026 (планирование): R_s(r_w) после останова в зависимости от h0 = time.dt_after_control_change.

Нарастание — штатное (FEAT-032): поле конфига, без подмены Simulator._advance
(проба feat-032/probes/ramp_probe.py после FEAT-032 несовместима: run() передаёт
_advance шестой аргумент depth).

Режимы (из numerical_solver/, P — путь к скрипту):
    .venv\\Scripts\\python P val004 <W, ч[/s]> <N|-> <h0|none> ...
        сценарий VAL-004 (tests/data/bug020_rs150): 10 сут добычи, затем W
        интервалов останова по 1 ч (нарастание — только на первом: дальше
        управление то же); N — число ячеек ('-' — как в конфиге, 350);
        W/s — каждый час делится на s интервалов (подшаги конца часа
        3600/s вместо 1800 с; dt_integration = 1 сут, каждый интервал — один шаг)
    .venv\\Scripts\\python P octave <F> <j> ...
        сценарий VAL-004, первый час останова заданными шагами (нарастание
        выключено): первый шаг 3600/2**F при любом j; ступени 3600/2**(F-j),
        3600/2**(F-j), 3600/2**(F-j-1), ..., 1800 с, каждая поделена на 2**j
        равных шагов («2**j шагов на октаву»). j = 0 — штатное нарастание
        FEAT-032 с h0 = 3600/2**F; F = 9 + k, j = k — серия k VAL-004
    .venv\\Scripts\\python P example-octave <имя> <F> <j> ...
        пример: первый часовой интервал после смены управления заменён шагами
        режима octave (нарастание выключено, каждый шаг — интервал истории)
    .venv\\Scripts\\python P example <имя> <h0|none|asis> ...
        пример examples/<имя>; asis — конфиг как есть
В конце серии — разности соседних прогонов и оценка Ричардсона при q = 1
(соседние h0 должны отличаться вдвое).
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT.parent / "vault" / "issues" / "feat-032" / "probes"))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from ramp_probe import fingerprint  # noqa: E402  (только функция отпечатка)

DAY, HOUR, BAR = 86400.0, 3600.0, 1e5
VAL004 = SOLVER_ROOT / "tests" / "data" / "bug020_rs150" / "config.json"
N_PROD = 10


def parse_h0(a):
    return None if a == "none" else float(a)


def shut_time(sim):
    """Начало первого интервала со сменой управления, с."""
    t = 0.0
    ivs = sim._schedule.intervals
    for k, iv in enumerate(ivs):
        if k > 0 and iv.bc != ivs[k - 1].bc:
            return t
        t += iv.dt
    raise RuntimeError("смены управления нет")


def run(cfg, label):
    """Прогон с подсчётом подшагов и отказов гидродинамики после смены управления."""
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    t_shut = shut_time(sim)
    stats = {"ok": 0, "fail": 0, "first": None, "min_ok": np.inf, "where": []}
    solve = sim._hydro.solve

    # Обёртка: отказ (HydroConvergenceError) запускает дробление DEBT-015 —
    # шаги перестают быть заданными нарастанием; считаем отказы на останове.
    def counting(state, dt, bc):
        on_shut = state.t >= t_shut - 1e-6
        try:
            res = solve(state, dt, bc)
        except HydroConvergenceError:
            if on_shut:
                stats["fail"] += 1
                stats["where"].append(((state.t - t_shut) / HOUR, dt))
            raise
        if on_shut:
            stats["ok"] += 1
            stats["min_ok"] = min(stats["min_ok"], dt)
            if stats["first"] is None:
                stats["first"] = dt
        return res

    sim._hydro.solve = counting
    t0 = time.perf_counter()
    hist = sim.run(s0)
    wall = time.perf_counter() - t0
    times = np.array(hist.times)

    def rec(dt_after):
        i = int(np.argmin(np.abs(times - (t_shut + dt_after))))
        return hist.states[i] if abs(times[i] - t_shut - dt_after) < 1e-6 else None

    marks = {"1ч": rec(HOUR), "24ч": rec(DAY), "финал": hist.states[-1]}
    line = (f"{label}: первый подшаг {stats['first']:.5g} с, принято {stats['ok']}, "
            f"отказов {stats['fail']}, мин. принятый {stats['min_ok']:.4g} с, счёт {wall:.1f} с, "
            f"отпечаток {fingerprint(hist)}")
    print(line, flush=True)
    if stats["where"]:
        print("    отказы (ч от смены управления, dt с): " + ", ".join(
            f"({t:.4g}, {dt:.4g})" for t, dt in stats["where"][:12]), flush=True)
    for name, st in marks.items():
        if st is None:
            continue
        print(f"    {name}: R_s(r_w) {st.Rs[0]:.4f}, R_s[1] {st.Rs[1]:.4f}, "
              f"T(r_w) {st.T[0]:.4f} К, p(r_w) {st.p[0] / BAR:.4f} бар, "
              f"ячеек с газом {int(np.count_nonzero(st.Sg > 0))}", flush=True)
    return marks


def series_report(results):
    """Разности соседних прогонов (h0 вдвое меньше) и Ричардсон при q = 1 по R_s(r_w), T, p."""
    keys = [k for k in results if k is not None]
    for mark in ("1ч", "24ч", "финал"):
        rows = [(k, results[k][mark]) for k in keys if results[k].get(mark) is not None]
        if len(rows) < 2:
            continue
        print(f"  ряд по h0, {mark}:")
        for (k1, a), (k2, b) in zip(rows, rows[1:]):
            dRs = b.Rs[0] - a.Rs[0]
            dprof = float(np.max(np.abs(b.Rs - a.Rs)))
            rich = 2 * b.Rs[0] - a.Rs[0]
            print(f"    h0 {k1:g} -> {k2:g}: ΔR_s(r_w) {dRs:+.4f}, max|ΔR_s| профиля {dprof:.4f} "
                  f"(ячейка {int(np.argmax(np.abs(b.Rs - a.Rs)))}), Ричардсон R_s(r_w) {rich:.4f}; "
                  f"ΔT(r_w) {b.T[0] - a.T[0]:+.5f} К, Δp(r_w) {(b.p[0] - a.p[0]) / BAR:+.5f} бар")


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    mode = sys.argv[1]
    results = {}
    if mode == "val004":
        W, _, s = sys.argv[2].partition("/")
        W, s = int(W), int(s or 1)
        N = sys.argv[3]
        for a in sys.argv[4:]:
            h0 = parse_h0(a)
            cfg = load_config(VAL004)
            hist = cfg.time.history
            assert len(hist) == N_PROD + 1, "сценарий bug020_rs150 изменился"
            shut = copy.deepcopy(hist[N_PROD])
            shut.dt = HOUR / s     # 3600/s — двоичная дробь при s = 2**j: сумма точная
            cfg.time.history = list(hist[:N_PROD]) + [copy.deepcopy(shut) for _ in range(W * s)]
            if N != "-":
                cfg.grid.N = int(N)
            cfg.time.dt_after_control_change = h0
            results[h0] = run(cfg, f"val004 N={cfg.grid.N} W={W} ч, интервал {HOUR / s:g} с, h0={a}")
    elif mode == "octave":
        F, _, N = sys.argv[2].partition(":")     # «18:700» — F = 18 при N = 700
        F = int(F)
        for a in sys.argv[3:]:
            j = int(a)
            M = F - j
            cfg = load_config(VAL004)
            hist = cfg.time.history
            assert len(hist) == N_PROD + 1, "сценарий bug020_rs150 изменился"
            shut = hist[N_PROD]
            base = [HOUR / 2 ** M] + [HOUR / 2 ** i for i in range(M, 0, -1)]
            assert sum(base) == HOUR   # двоичные дроби: сумма точная
            tail = []
            for H in base:
                for _ in range(2 ** j):
                    x = copy.deepcopy(shut)
                    x.dt = H / 2 ** j
                    tail.append(x)
            cfg.time.history = list(hist[:N_PROD]) + tail
            cfg.time.dt_after_control_change = None
            if N:
                cfg.grid.N = int(N)
            # ключ ряда — j (первый шаг у всех прогонов один и тот же)
            results[float(j)] = run(
                cfg, f"octave N={cfg.grid.N} F={F} (первый {HOUR / 2 ** F:.4g} с), j={j}, "
                     f"шагов {len(tail)}")
    elif mode == "example-octave":
        name, F = sys.argv[2], int(sys.argv[3])
        for a in sys.argv[4:]:
            j = int(a)
            M = F - j
            cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
            hist = cfg.time.history
            # первый интервал со сменой управления — по полям управления
            key = [(h.control, h.p_wf, h.q_oil) for h in hist]
            k = next(i for i in range(1, len(hist)) if key[i] != key[i - 1])
            assert hist[k].dt == HOUR, f"интервал {k} не часовой: {hist[k].dt}"
            base = [HOUR / 2 ** M] + [HOUR / 2 ** i for i in range(M, 0, -1)]
            assert sum(base) == HOUR
            tail = []
            for H in base:
                for _ in range(2 ** j):
                    x = copy.deepcopy(hist[k])
                    x.dt = H / 2 ** j
                    tail.append(x)
            cfg.time.history = list(hist[:k]) + tail + list(hist[k + 1:])
            cfg.time.dt_after_control_change = None
            assert cfg.time.dt_integration >= HOUR / 2   # каждый интервал — один шаг
            results[float(j)] = run(
                cfg, f"{name} octave F={F} (первый {HOUR / 2 ** F:.4g} с), j={j}, шагов {len(tail)}")
    elif mode == "example":
        name = sys.argv[2]
        for a in sys.argv[3:]:
            cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
            if a != "asis":
                cfg.time.dt_after_control_change = parse_h0(a)
            h0 = cfg.time.dt_after_control_change
            results[h0] = run(cfg, f"{name} h0={a} ({h0})")
    else:
        raise SystemExit(f"неизвестный режим {mode}")
    series_report(results)


if __name__ == "__main__":
    main()
