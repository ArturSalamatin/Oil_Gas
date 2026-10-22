"""FEAT-032 (планирование): нарастающий шаг после смены управления — вариант 2.

Вариант 2: на первом шаге интервала, где сменилось управление скважиной,
локальное дробление G1a (Simulator._advance, DEBT-015) стартует не с полного
шага dt, а с подшага dt/2**m — наименьшее m, при котором dt/2**m <= h0.
Дальше — штатный рост x2 с выравниванием. Шаг меряется в единицах
dt/2**(max_retries + m): дробление отказа идёт на max_retries уровней ниже h0.
При m = 0 код побитово равен Simulator._advance (проверяется: базовый прогон
печатает отпечаток истории, сравнить с прогоном без подмены — режим "orig").

Пакет не правится: подменяется sim._advance экземпляра.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P val004 <W, ч> <h0|none> ...      — сценарий VAL-004
    .venv\\Scripts\\python P example <имя> <first:0|1> <h0|none|orig> ...
"""

import copy
import hashlib
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.bc import PressureControl, RateControl  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402

DAY, HOUR, BAR = 86400.0, 3600.0, 1e5
VAL004 = SOLVER_ROOT / "tests" / "data" / "bug020_rs150" / "config.json"
# Пределы Δt -> 0 (VAL-004, limits.out.txt; сутки — аудит плана VAL-004, раздел 1.4)
LIM = {"1h": {"p": 185.4611262, "T": 398.0232431, "Rs": 41.2},
       "24h": {"p": 224.7314902, "T": 399.0194629, "Rs": 41.2}}


def control_key(well):
    """Управление как значение: тип + параметры (у классов bc.py нет __eq__)."""
    if isinstance(well, PressureControl):
        return ("pressure", well.p_wf)
    if isinstance(well, RateControl):
        return ("rate", well.q_oil, well.min_bhp)
    raise TypeError(type(well))


def depth(dt, h0):
    """Наименьшее m >= 0, при котором dt/2**m <= h0."""
    m = 0
    while dt / 2 ** m > h0:
        m += 1
    return m


def ramp_advance(sim, state, dt, bc, balance, mass, m, stats):
    """Simulator._advance (G1a) с начальным подшагом dt/2**m; при m = 0 — штатный."""
    n_units = 2 ** (sim._max_retries + m)
    done = 0
    size = 2 ** sim._max_retries          # = n_units при m = 0
    n_ok = n_fail = 0
    while done < n_units:
        h = dt / (n_units // size)
        try:
            hydro_result = sim._hydro.solve(state, h, bc)
        except HydroConvergenceError as exc:
            n_fail += 1
            stats.setdefault("exc", []).append(str(exc))
            if size == 1:
                raise RuntimeError(f"не сошлось на наименьшем подшаге {h:.3e} с, "
                                   f"t = {state.t / DAY:.6f} сут") from exc
            size //= 2
            continue
        if mass is not None:
            mass.add_step(hydro_result)
        T_new = sim._energy.solve(hydro_result, state, h, bc, collect=balance)
        sim._check_temperature(T_new, h, hydro_result.state.t)
        state = SimulationState(
            p=hydro_result.state.p, Sg=hydro_result.state.Sg,
            Rs=hydro_result.state.Rs, T=T_new,
            regime=hydro_result.state.regime, t=hydro_result.state.t)
        n_ok += 1
        done += size
        if done < n_units and done % (2 * size) == 0:
            size *= 2
    stats["ok"] += n_ok
    stats["fail"] += n_fail
    return state, hydro_result


def patch(sim, h0, include_first):
    """Подменить sim._advance: нарастание на первом шаге интервала со сменой управления."""
    stats = {"ok": 0, "fail": 0, "ramps": [], "first_steps": []}
    seen = {"bc": None, "key": None}

    def advance(state, dt, bc, balance, mass):
        m = 0
        if bc is not seen["bc"]:                      # первый шаг нового интервала
            key = control_key(bc.well)
            changed = (key != seen["key"]) if seen["key"] is not None else include_first
            seen["bc"], seen["key"] = bc, key
            if changed and h0 is not None:
                m = depth(dt, h0)
                stats["ramps"].append((state.t, dt, m, dt / 2 ** m))
        return ramp_advance(sim, state, dt, bc, balance, mass, m, stats)

    sim._advance = advance
    return stats


def fingerprint(hist):
    """Отпечаток истории: sha256 всех полей всех записей."""
    hsh = hashlib.sha256()
    for st in hist.states:
        for f in ("p", "Sg", "Rs", "T"):
            hsh.update(np.ascontiguousarray(getattr(st, f), dtype=float).tobytes())
    return hsh.hexdigest()[:16]


def record(hist, t):
    i = int(np.argmin(np.abs(np.array(hist.times) - t)))
    assert abs(hist.times[i] - t) < 1e-6, (hist.times[i], t)
    return hist.states[i]


def run_val004(W_h, h0):
    """VAL-004: 10 сут добычи (шаг 1 сут), останов W_h ч интервалами по 1 ч."""
    cfg = load_config(VAL004)
    cfg.output.log_level = "ERROR"
    prod, shut = cfg.time.history[:10], cfg.time.history[10]
    tail = []
    for _ in range(int(W_h)):
        x = copy.deepcopy(shut)
        x.dt = HOUR
        tail.append(x)
    cfg.time.history = list(prod) + tail
    sim, s0 = SimulatorFactory.from_config(cfg)
    stats = patch(sim, h0, include_first=False)
    t0 = time.perf_counter()
    hist = sim.run(s0)
    el = time.perf_counter() - t0
    line = f"h0={'нет' if h0 is None else f'{h0:g} с':>8}"
    if stats["ramps"]:
        _, dt, m, h = stats["ramps"][0]
        line += f" (m={m}, первый подшаг {h:.4g} с)"
    for tag, t in (("1h", 10 * DAY + HOUR), ("24h", 10 * DAY + 24 * HOUR)):
        if t > hist.times[-1] + 1e-6:
            continue
        st = record(hist, t)
        p, T, Rs = st.p[0] / BAR, st.T[0], st.Rs[0]
        L = LIM[tag]
        line += (f" | {tag}: p={p:.4f} ({p - L['p']:+.3f}) T={T:.4f} ({T - L['T']:+.4f})"
                 f" Rs={Rs:.2f} ({Rs - L['Rs']:+.1f})")
    line += f" | подшагов {stats['ok']}, отказов {stats['fail']}, счёт {el:.1f} с"
    print(line, flush=True)


def run_example(name, include_first, h0, orig=False):
    """Пример: прогон с подменой (или без — orig); отпечаток, сводка T(r_w), Rs(r_w)."""
    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    stats = None if orig else patch(sim, h0, include_first)
    t0 = time.perf_counter()
    try:
        hist = sim.run(s0)
    except RuntimeError as exc:
        print(f"{name} first={int(include_first)} h0={h0}: ОТКАЗ — {exc}", flush=True)
        if stats is not None:
            ex = stats.get("exc", [])
            for msg in (ex[:2] + ["…"] + ex[-2:]) if len(ex) > 4 else ex:
                print(f"    {msg}", flush=True)
        return None
    el = time.perf_counter() - t0
    tag = "orig" if orig else f"h0={'нет' if h0 is None else f'{h0:g}'} first={int(include_first)}"
    line = f"{name} {tag}: записей {len(hist.times)}, отпечаток {fingerprint(hist)}, счёт {el:.1f} с"
    if stats is not None:
        line += f", подшагов {stats['ok']}, отказов {stats['fail']}, нарастаний {len(stats['ramps'])}"
        if stats["ramps"]:
            ms = sorted({(m, round(h, 4)) for _, _, m, h in stats["ramps"]})
            line += f" (m, h0: {ms})"
    print(line, flush=True)
    return hist


def compare(name, base, other, label):
    """Сводка отличий other от base по забойной ячейке: max |Δ| по записям и где."""
    t = np.array(base.times) / DAY
    T0 = np.array([s.T[0] for s in base.states])
    T1 = np.array([s.T[0] for s in other.states])
    R0 = np.array([s.Rs[0] for s in base.states])
    R1 = np.array([s.Rs[0] for s in other.states])
    p0 = np.array([s.p[0] for s in base.states]) / BAR
    p1 = np.array([s.p[0] for s in other.states]) / BAR
    iT, iR, ip = (int(np.argmax(np.abs(a - b))) for a, b in ((T1, T0), (R1, R0), (p1, p0)))
    print(f"  {name} {label} против штатного: max|ΔT(r_w)| = {abs(T1[iT] - T0[iT]):.4f} К "
          f"(t = {t[iT]:.4f} сут, {T0[iT]:.4f} → {T1[iT]:.4f}); "
          f"max|ΔRs(r_w)| = {abs(R1[iR] - R0[iR]):.2f} (t = {t[iR]:.4f} сут, "
          f"{R0[iR]:.2f} → {R1[iR]:.2f}); max|Δp(r_w)| = {abs(p1[ip] - p0[ip]):.3f} бар "
          f"(t = {t[ip]:.4f} сут); на конце: ΔT = {T1[-1] - T0[-1]:+.4f} К", flush=True)


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    mode = sys.argv[1]
    if mode == "val004":
        W_h = float(sys.argv[2])
        for a in sys.argv[3:]:
            run_val004(W_h, None if a == "none" else float(a))
    elif mode == "example":
        name, first = sys.argv[2], bool(int(sys.argv[3]))
        base = run_example(name, first, None, orig=True)
        for a in sys.argv[4:]:
            if a == "none":
                # m = 0 везде: ramp_advance обязан совпасть с Simulator._advance побитово
                run_example(name, first, None)
                continue
            h = run_example(name, first, float(a))
            if h is not None and base is not None:
                compare(name, base, h, f"h0={a} first={int(first)}")


if __name__ == "__main__":
    main()
