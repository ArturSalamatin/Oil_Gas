r"""DEBT-068: что делает расчёт при c_r < 0 — проба красного состояния (план).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-068\probes\red_state.py
Конфиг примера 18 (единственный с c_r ≠ 0), история укорочена до двух суток:
сутки при p_wf = 15 МПа, сутки при 10 МПа. Подменяется только rock.compressibility.
Печатается: пороги сжимаемостей флюида из PVT задачи (C_p < 0 при c_r < −c),
проходит ли load_config, итог расчёта, число не сошедшихся подшагов (dev_log
Simulator._advance), дебит нефти в конце суток, диапазоны p и φ(p).
"""
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver import simulator  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.pvt.consistency import (  # noqa: E402
    gas_compressibility, saturated_oil_compressibility, undersaturated_oil_compressibility)

EXAMPLE = SOLVER / "examples" / "18_prototype_input"
WORK = Path(__file__).resolve().parent / "red_state_tmp"
DAY = 86400.0
# Записи — каждый час: знак C_p проверяется по записанным состояниям
HISTORY = [{"duration": DAY, "dt_out": 3600.0, "control": "pressure", "p_wf": 15e6},
           {"duration": DAY, "dt_out": 3600.0, "control": "pressure", "p_wf": 10e6}]
# 4.5e-10 — значение примера 18 (книга прототипа); остальные — ошибка знака
# и значения порядка сжимаемости недонасыщенной нефти и больше
C_R = (4.5e-10, 0.0, -4.5e-10, -1e-9, -2e-9, -4.5e-9, -2e-8)


class Counter(logging.Handler):
    """Считает записи журнала решателя: не сошедшиеся подшаги и дробления шага."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.failed = 0
        self.split = 0

    def emit(self, record):
        msg = record.getMessage()
        if "не сошёлся" in msg:
            self.failed += 1
        elif "раздроблен" in msg:
            self.split += 1


def config_path(c_r: float) -> Path:
    """config.json примера 18 с укороченной историей и подменённым c_r; таблицы — из примера."""
    raw = json.loads((EXAMPLE / "config.json").read_text(encoding="utf-8"))
    raw["time"]["history"] = HISTORY
    raw["rock"]["compressibility"] = c_r
    for key in ("oil_pvt_file", "gas_pvt_file"):
        raw["pvt"][key] = str(EXAMPLE / raw["pvt"][key])
    raw["relperm"]["file"] = str(EXAMPLE / raw["relperm"]["file"])
    path = WORK / f"config_{c_r:+.2e}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def thresholds() -> None:
    """Сжимаемости флюида по PVT примера 18: C_p < 0 в ячейке, где c_r < −(S_o c_ot + S_g c_g)."""
    cfg = load_config(config_path(0.0))
    sim, _ = SimulatorFactory.from_config(cfg)
    pvt, ic = sim.pvt, cfg.initial_conditions
    p_b = float(pvt.pb(np.array([ic.Rs0]))[0])
    p_lo = min(h["p_wf"] for h in HISTORY)
    print(f"p0 = {ic.p0 / 1e6:g} МПа, R_s0 = {ic.Rs0:g}, p_b(R_s0) = {p_b / 1e6:.4g} МПа, "
          f"наименьшее p_wf = {p_lo / 1e6:g} МПа")
    # Узел p_b исключён: центральная разность там захватывает излом таблицы
    # (ветвь R_s0 и кривая насыщения) и даёт половину наклона — c_o = 6e-10
    # вместо 1.2e-9 1/Па на всём (p_b, p0]
    eps = 1e-4
    p_u = np.linspace(max(p_b, p_lo) * (1 + eps), ic.p0, 201)
    c_o = undersaturated_oil_compressibility(pvt, p_u, ic.Rs0)
    print(f"недонасыщенная нефть c_o, p ∈ [{p_u[0] / 1e6:.4g}, {ic.p0 / 1e6:g}] МПа: "
          f"{c_o.min():.3g} … {c_o.max():.3g} 1/Па → C_p < 0 при c_r < {-c_o.min():.3g}")
    if p_b > p_lo:
        p_s = np.linspace(p_lo, p_b * (1 - eps), 201)
        c_ot = saturated_oil_compressibility(pvt, p_s)
        c_g = gas_compressibility(pvt, p_s)
        print(f"насыщенная нефть c_ot, p ∈ [{p_lo / 1e6:g}, {p_b / 1e6:.4g}] МПа: "
              f"{c_ot.min():.3g} … {c_ot.max():.3g} 1/Па (при S_g → 0 C_p < 0 при "
              f"c_r < {-c_ot.min():.3g}); газ c_g: {c_g.min():.3g} … {c_g.max():.3g} 1/Па")


def negative_cp_cells(pvt, hist, c_r: float) -> str:
    """Недонасыщенные ячейки записей с c_r + c_o < 0 — там C_p < 0 (eq:Cp при S_g = 0)."""
    worst, n_under = 0, 0
    for s in hist.states:
        under = s.regime != 1          # 1 — двухфазная ячейка (state.py)
        p, rs = s.p[under], s.Rs[under]
        if p.size == 0:
            continue
        h = 1e-6 * p                   # шаг разности — как в pvt/consistency.py
        c_o = -(pvt.Bo(p + h, rs) - pvt.Bo(p - h, rs)) / (2.0 * h) / pvt.Bo(p, rs)
        k = int(np.count_nonzero(c_r + c_o < 0.0))
        if (k, p.size) > (worst, n_under):
            worst, n_under = k, p.size
    return (f"C_p < 0 (c_r + c_o < 0) — до {worst} ячеек из {n_under} недонасыщенных "
            f"в записи")


def run_case(c_r: float) -> str:
    """Один расчёт: итог одной строкой."""
    log = logging.getLogger("gpn_multiphase_solver")
    counter = Counter()
    log.handlers[:] = [counter]   # setup_logging не добавит вывод в консоль
    stage = "load_config"
    t0 = time.perf_counter()
    try:
        cfg = load_config(config_path(c_r))
        stage = "from_config"
        sim, state = SimulatorFactory.from_config(cfg)
        log.setLevel(logging.DEBUG)   # dev_log: «подшаг … не сошёлся»
        stage = "run"
        hist = sim.run(state)
    except Exception as e:  # noqa: BLE001 — проба печатает любой отказ
        msg = str(e).splitlines()[0] if str(e) else ""
        return (f"{stage}: {type(e).__name__}: {msg[:140]}  "
                f"[не сошлось подшагов {counter.failed}, {time.perf_counter() - t0:.0f} с]")
    p_all = np.concatenate([s.p for s in hist.states])
    phi = cfg.rock.porosity * np.exp(c_r * (p_all - cfg.initial_conditions.p0))
    # Время копится по подшагам — сравнение с концами суток с допуском
    days = [w.q_o_std * DAY for t, w in zip(hist.times, hist.well_data)
            if np.isclose(t, DAY) or np.isclose(t, 2 * DAY)]
    return (f"прошёл: не сошлось подшагов {counter.failed}, дроблений {counter.split}; "
            f"q_o на 1, 2 сут = {', '.join(f'{q:.4g}' for q in days)} м³ст/сут; "
            f"p {p_all.min() / 1e6:.4g}…{p_all.max() / 1e6:.4g} МПа; "
            f"φ {phi.min():.6g}…{phi.max():.6g}; {negative_cp_cells(sim.pvt, hist, c_r)}; "
            f"{time.perf_counter() - t0:.0f} с")


def shut_in_max_p(example: str, history=None) -> str:
    """Останов: max p − p0 по записям истории (верхняя граница c_r не нужна, если p ≤ p0)."""
    ex = SOLVER / "examples" / example
    raw = json.loads((ex / "config.json").read_text(encoding="utf-8"))
    if history is not None:
        raw["time"]["history"] = history
        raw["time"]["dt_after_control_change"] = 0.11
    for key in ("oil_pvt_file", "gas_pvt_file"):
        raw["pvt"][key] = str(ex / raw["pvt"][key])
    raw["relperm"]["file"] = str(ex / raw["relperm"]["file"])
    path = WORK / f"shut_in_{example}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    logging.getLogger("gpn_multiphase_solver").handlers[:] = [Counter()]
    cfg = load_config(path)
    sim, state = SimulatorFactory.from_config(cfg)
    hist = sim.run(state)
    p0, c_r = cfg.initial_conditions.p0, cfg.rock.compressibility
    dp = max(float(s.p.max()) - p0 for s in hist.states)
    phi_max = cfg.rock.porosity * np.exp(c_r * dp)
    return (f"{example}: c_r = {c_r:.3g} 1/Па, записей {len(hist.times)}, "
            f"t_end = {hist.times[-1] / DAY:g} сут; max(p) − p0 = {dp:.6g} Па; "
            f"max φ = {phi_max:.9g} (porosity = {cfg.rock.porosity:g})")


# Пример 18 (c_r > 0): сутки добычи при 10 МПа, затем сутки останова — как в
# примере 16: управление по дебиту q_oil = 0, первый подшаг 0.11 с (BUG-026)
SHUT_IN_18 = [{"dt": DAY, "control": "pressure", "p_wf": 10e6},
              {"duration": DAY, "dt_out": 3600.0, "control": "rate",
               "q_oil": 0.0, "min_bhp": 101325.0}]


if __name__ == "__main__":
    print(f"Код: {Path(simulator.__file__).resolve()}")
    WORK.mkdir(exist_ok=True)
    try:
        thresholds()
        print()
        for c_r in C_R:
            print(f"c_r = {c_r:+.2e} 1/Па: {run_case(c_r)}", flush=True)
        print("\nОстанов: превышает ли p начальное p0 (записи истории, не все подшаги)")
        print(shut_in_max_p("16_well_shut_in"), flush=True)
        print(shut_in_max_p("18_prototype_input", SHUT_IN_18), flush=True)
    finally:
        for f in WORK.glob("*.json"):
            f.unlink()
        WORK.rmdir()
