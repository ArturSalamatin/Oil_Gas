"""VAL-004 (планирование): сходимость по шагу останова на сценарии bug020_rs150.

Добыча — как в конфиге теста (10 интервалов по 1 сут, dt_integration = 1 сут,
один шаг на интервал), поэтому состояние на конец добычи побитово одно и то
же во всех прогонах (проверяется). Останов (q_oil = 0) длиной W разбит на
интервалы истории длиной h = 3600/2**k: при dt_integration = 1 сут каждый
интервал — ровно один шаг h, если гидродинамика сошлась (иначе локальное
дробление DEBT-015 — печатается).

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P <W, ч> <k_min> <k_max> [m [j_tail [j_cap]]]
m — первый час нарастающими шагами от 3600/2**m (base_steps), j_cap — их
предел 3600/2**j_cap, j_tail — шаг после первого часа 3600/2**j_tail;
сгущение k делит на 2**k каждый шаг, отношение шагов сохраняется.
Профили на отметках 1 ч и W — в dt_series_W<W>h_k<k_min>-<k_max>.npz рядом
со скриптом.
"""

import copy
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CFG = SOLVER_ROOT / "tests" / "data" / "bug020_rs150" / "config.json"
DAY, HOUR, BAR = 86400.0, 3600.0, 1e5
FIELDS = ("p", "Sg", "Rs", "T")


def base_steps(W_h, m, j_tail=0, j_cap=0):
    """Шаги останова до сгущения: m = None — по 3600 с; иначе первый час
    нарастающими шагами 3600/2**m, 3600/2**m, 3600/2**(m-1), …, до
    3600/2**(j_cap+1) (сумма ровно 3600/2**j_cap), остаток часа — по
    3600/2**j_cap; при j_cap = 0 — до 1800 с, сумма 3600 с. Дальше по
    3600/2**j_tail с. Аудит: m = 13, j_cap = j_tail = 5 — первый час от 0.44 с
    до 56.25 с, затем всё по 112.5 с: шаги без отказов (серии 1 ч и 24 ч)."""
    n_h = int(round(W_h))
    if m is None:
        return [HOUR] * n_h
    first = [HOUR / 2 ** m] + [HOUR / 2 ** j for j in range(m, j_cap, -1)]
    first += [HOUR / 2 ** j_cap] * (2 ** j_cap - 1)
    return first + [HOUR / 2 ** j_tail] * ((n_h - 1) * 2 ** j_tail)


def run(W_h, k, m=None, j_tail=0, j_cap=0):
    """Прогон: останов W_h часов, каждый шаг base_steps делится на 2**k; профили на 1 ч и на W."""
    cfg = load_config(CFG)
    cfg.output.log_level = "ERROR"
    prod, shut = cfg.time.history[:10], cfg.time.history[10]
    h = HOUR / 2 ** k
    tail = []
    for H in base_steps(W_h, m, j_tail, j_cap):
        for _ in range(2 ** k):
            x = copy.deepcopy(shut)
            x.dt = H / 2 ** k
            tail.append(x)
    cfg.time.history = list(prod) + tail
    sim, s0 = SimulatorFactory.from_config(cfg)

    # Учёт подшагов гидродинамики на останове: h принятых и число отказов
    acc, fails = Counter(), [0]
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        try:
            r = orig(state, dt, bc)
        except Exception:
            if state.t >= 10 * DAY - 1e-6:
                fails[0] += 1
            raise
        if state.t >= 10 * DAY - 1e-6:
            acc[round(dt, 6)] += 1
        return r

    sim._hydro.solve = solve
    t0 = time.perf_counter()
    hist = sim.run(s0)
    el = time.perf_counter() - t0
    times = np.array(hist.times)
    out = {}
    for tag, t in (("1h", 10 * DAY + HOUR), ("W", 10 * DAY + W_h * HOUR)):
        i = int(np.argmin(np.abs(times - t)))
        assert abs(times[i] - t) < 1e-6, (times[i], t)
        st = hist.states[i]
        for f in FIELDS:
            out[f"{tag}_{f}"] = np.array(getattr(st, f), float)
        out[f"{tag}_regime"] = np.array(st.regime)
        out[f"{tag}_pwf"] = float(hist.well_data[i].p_wf)
    # Состояние на конец добычи (запись 10) — для проверки побитового совпадения
    out["prod_p"] = np.array(hist.states[10].p)
    out["prod_T"] = np.array(hist.states[10].T)
    return out, el, acc, fails[0], h


def main():
    W_h, k_min, k_max = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    m = int(sys.argv[4]) if len(sys.argv) > 4 else None
    j_tail = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    j_cap = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    grade = ("равномерно по 3600/2**k" if m is None else
             f"первый час нарастающими шагами от 3600/2**{m} до 3600/2**{j_cap + 1}, остаток "
             f"часа по 3600/2**{j_cap}, дальше по 3600/2**{j_tail}; всё делится на 2**k")
    print(f"останов {W_h:g} ч, k = {k_min}..{k_max}; {grade}", flush=True)
    res = {}
    prod_ref = None
    for k in range(k_min, k_max + 1):
        out, el, acc, nf, h = run(W_h, k, m, j_tail, j_cap)
        res[k] = out
        if prod_ref is None:
            prod_ref = (out["prod_p"], out["prod_T"])
        same = (np.array_equal(prod_ref[0], out["prod_p"])
                and np.array_equal(prod_ref[1], out["prod_T"]))
        sub = ", ".join(f"{a:g}×{b}" for a, b in sorted(acc.items()))
        line = (f"k={k} h={h:9.4f} с | 1 ч: p0={out['1h_p'][0] / BAR:.7f} бар "
                f"T0={out['1h_T'][0]:.7f} К 2ф={int(np.sum(out['1h_regime'] == 1))} "
                f"maxSg={out['1h_Sg'].max():.4f}")
        if W_h != 1:
            line += (f" | {W_h:g} ч: p0={out['W_p'][0] / BAR:.7f} бар "
                     f"T0={out['W_T'][0]:.7f} К Rs0={out['W_Rs'][0]:.4f} "
                     f"2ф={int(np.sum(out['W_regime'] == 1))}")
        line += (f" | добыча побитово {'да' if same else 'НЕТ'}; отказов {nf}; "
                 f"подшаги: {sub}; счёт {el:.1f} с")
        print(line, flush=True)
    tag = "" if m is None else (f"_g{m}" + (f"t{j_tail}" if j_tail else "")
                                + (f"c{j_cap}" if j_cap else ""))
    np.savez(HERE / f"dt_series_W{W_h:g}h_k{k_min}-{k_max}{tag}.npz",
             **{f"k{k}_{key}": v for k, o in res.items() for key, v in o.items()})


if __name__ == "__main__":
    main()
