"""DEBT-073: порог S_g ≤ 0.98 прототипа — что будет с отвергнутым корнем, если порог поднять.

Сценарий — пример 05 (Стендинг, таблица ОФП), первые 6 ч, таблица ОФП до S_g = 0.01
(k_ro = 0.98, k_rg = 0.001 на краю; vault/issues/debt-071/probes/relperm_to_001.csv).
С порогом 0.98 ступень 4 сходится (невязка 5.5e-14) к корню с S_g > 0.98 и отвергает его
(debt-071/probes/scenarios_v1_to001.out.txt).

Порог 0.98 стоит в двух местах blackoil.py: _trial_is_reasonable (пробные точки ступеней 1–3)
и _newton_switching (корень ступени 4). Подмена — в памяти: исходный текст обоих методов,
0.98 → новое значение, exec в пространстве имён модуля. Файлы прототипа не меняются.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-073\\probes\\sg_bound_scan.py
"""
import inspect
import logging
import re
import textwrap
import time
from pathlib import Path

import numpy as np

import gpn_multiphase_solver
import radial_blackoil
import radial_blackoil.blackoil as bo
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.units import DAY_TO_S

SOLVER = Path.cwd()
HERE = Path(__file__).resolve().parent
RELPERM = HERE.parent.parent / "debt-071" / "probes" / "relperm_to_001.csv"
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
print(f"прототип: {Path(radial_blackoil.__file__).parent}", flush=True)

# Исходные методы — до любой подмены; inspect.getsource читает их текст из файла
ORIG = {name: getattr(bo.RadialBlackOilModel, name)
        for name in ("_trial_is_reasonable", "_newton_switching")}


def set_sg_bound(expr: str) -> None:
    """Порог S_g двухфазных ячеек в обоих методах: 0.98 → expr (текст выражения Python)."""
    for name, func in ORIG.items():
        src = textwrap.dedent(inspect.getsource(func))
        # в _trial_is_reasonable — одно вхождение (код), в _newton_switching — два (комментарий и код)
        assert "0.98" in src, name
        src = src.replace("0.98", expr)
        ns = {}
        exec(compile(src, f"<{name}, порог {expr}>", "exec"), bo.__dict__, ns)
        setattr(bo.RadialBlackOilModel, name, ns[name])


# ── Учёт принятых состояний: max S_g у забоя и по пласту, время ──
TRACE = []
_orig_solve = PrototypeHydroAdapter.solve


def solve(self, state, dt, bc):
    res = _orig_solve(self, state, dt, bc)
    sg = res.state.Sg
    TRACE.append((state.t + dt, dt, float(sg[0]), float(np.max(sg)), int(np.argmax(sg)),
                  float(res.state.p[0])))
    return res


PrototypeHydroAdapter.solve = solve


# Сценарии замера DEBT-071 (vault/issues/debt-071/probes/scenarios.out.txt, cut21.out.txt):
# пример, таблица ОФП, число интервалов истории (05 — по 1 ч, 21 — по 1 сут), R_s0.
# Второй и третий отказывают на первом подшаге — принятых состояний нет.
CASES = {
    "05_to001": ("05_standing_table_rp", RELPERM, 6, None),
    "05_rs100_to01": ("05_standing_table_rp", RELPERM.with_name("relperm_to_01.csv"), 6, 100.0),
    "21_to03": ("21_rs100_cooling", RELPERM.with_name("relperm_corey21_to_0.3.csv"), 1, None),
}


def run(expr: str, hours: int = 6, patch: bool = True, case: str = "05_to001"):
    # patch=False — порог уже подставлен вызывающим (rejected_roots: обёртка поверх подмены)
    if patch:
        set_sg_bound(expr)
    example, relperm, n_hist, rs0 = CASES[case]
    if case != "05_to001":
        hours = n_hist
    cfg = load_config(SOLVER / "examples" / example / "config.json")
    # 21 — Кори в конфиге; таблица — та же Кори, протабулированная до 0.3 (cut21 пробы DEBT-071)
    cfg.relperm.model = "table"
    cfg.relperm.file = str(relperm)
    # load_config разворачивает историю в интервалы по dt_out (05: 72 по 1 ч)
    cfg.time.history = cfg.time.history[:hours]
    if rs0 is not None:
        cfg.initial_conditions.Rs0 = rs0
    print(f"\n### сценарий {case}: {example}, ОФП {relperm.name}, интервалов {hours}, R_s0 = "
          f"{cfg.initial_conditions.Rs0}", flush=True)
    TRACE.clear()
    t0 = time.perf_counter()
    status = "дошёл до конца"
    try:
        sim, s0 = SimulatorFactory.from_config(cfg)
        logging.getLogger("gpn_multiphase_solver").setLevel(logging.ERROR)
        sim.run(s0)
    except Exception as exc:  # noqa: BLE001 — проба: печать причины
        msg = str(exc)
        head = msg.split(":")[0]
        m = re.search(r"попытки ступеней: \[(.*?)\]", msg, re.S)
        status = f"отказ ({type(exc).__name__}): {head[:110]}"
        if m:
            status += "\n      попытки: " + " ".join(m.group(1).split())
        elif "Последний отказ" not in msg:
            status += "\n      текст: " + " ".join(msg.split())[:400]
    wall = time.perf_counter() - t0
    print(f"\n=== порог S_g {expr}: {status}", flush=True)
    print(f"    принятых подшагов {len(TRACE)}, {wall:.1f} с")
    if TRACE:
        tl, dtl, sg0, sgmax, jmax, p0 = TRACE[-1]
        top = max(TRACE, key=lambda r: r[3])
        print(f"    последнее принятое: t = {tl:.1f} с, dt = {dtl:.3g} с, S_g[0] = {sg0:.6f}, "
              f"max S_g = {sgmax:.6f} (ячейка {jmax}), p[0] = {p0 / 1e6:.4f} МПа")
        print(f"    максимум по расчёту: S_g = {top[3]:.6f} (ячейка {top[4]}) при t = {top[0]:.1f} с")
        # Первые моменты, когда max S_g перешёл пороги — темп роста у забоя
        for edge in (0.9, 0.98, 0.99, 0.999, 1.0):
            hit = next((r for r in TRACE if r[3] > edge), None)
            if hit:
                print(f"    max S_g > {edge}: впервые при t = {hit[0]:.1f} с (dt = {hit[1]:.3g} с, "
                      f"S_g = {hit[3]:.6f})")
        # Траектория у забоя: последние 8 принятых подшагов
        print("    последние подшаги (t, с | dt, с | S_g[0] | p[0], МПа):")
        for t, d, s, _, _, p in TRACE[-8:]:
            print(f"      {t:10.2f} | {d:8.3g} | {s:.6f} | {p / 1e6:.4f}")


def rejected_roots(case: str = "05_to001"):
    """Порог 0.98: S_g отвергнутых корней ступени 4 (выход 'sg_bound') — где корень на самом деле."""
    set_sg_bound("0.98")
    patched = bo.RadialBlackOilModel._newton_switching
    seen = []

    def wrapped(self, state_old, dt_s, *args, **kwargs):
        new, rep = patched(self, state_old, dt_s, *args, **kwargs)
        if getattr(rep, "exit_reason", "") == "sg_bound":
            sg = np.asarray(new.sg, float)
            seen.append((dt_s, float(sg[0]), float(np.max(sg)), int(np.count_nonzero(sg > 0.98)),
                         float(new.pressure_bar[0])))
        return new, rep

    bo.RadialBlackOilModel._newton_switching = wrapped
    try:
        run("0.98", patch=False, case=case)
    finally:
        bo.RadialBlackOilModel._newton_switching = patched
    print(f"\n    отвергнутых корней ступени 4: {len(seen)} (dt, с | S_g[0] | max S_g | ячеек > 0.98 | p[0], бар)")
    for dt_s, s0, smax, n, p0 in seen:
        print(f"      {dt_s:8.3g} | {s0:.6f} | {smax:.6f} | {n} | {p0:.4f}")


def first_substep_21():
    """Пример 21, один шаг 168.75 с (наименьший подшаг отказа 21_to03) от t = 0: таблица Кори до 1.0 и до 0.3.

    Таблица до 0.3 совпадает с полной при S_g <= 0.3 (те же узлы). Если решение с полной
    таблицей нигде не выше 0.3, оно — решение и задачи с обрезанной таблицей: физическое
    решение есть, отказ — алгоритма.
    """
    from dataclasses import replace
    set_sg_bound("0.98")
    for name in ("relperm_corey21_to_1.csv", "relperm_corey21_to_0.3.csv"):
        cfg = load_config(SOLVER / "examples" / "21_rs100_cooling" / "config.json")
        cfg.relperm.model = "table"
        cfg.relperm.file = str(RELPERM.with_name(name))
        dt = 86400.0 / 512
        cfg.time.dt_integration = dt
        cfg.time.history = [replace(cfg.time.history[0], dt=dt)]
        TRACE.clear()
        try:
            sim, s0 = SimulatorFactory.from_config(cfg)
            logging.getLogger("gpn_multiphase_solver").setLevel(logging.ERROR)
            sim.run(s0)
            status = "принят"
        except Exception as exc:  # noqa: BLE001 — проба: печать причины
            m = re.search(r"попытки ступеней: \[(.*?)\]", str(exc), re.S)
            status = "отказ: " + (" ".join(m.group(1).split()) if m else str(exc)[:200])
        print(f"\n21, {name}, шаг {dt:g} с от t = 0: {status}")
        for t, d, s0_, smax, jmax, p0 in TRACE:
            print(f"    t = {t:.2f} с, dt = {d:.4g} с: S_g[0] = {s0_:.6f}, max S_g = {smax:.6f} "
                  f"(ячейка {jmax}), p[0] = {p0 / 1e6:.4f} МПа")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["21-first"]:
        first_substep_21()
        sys.exit()
    if sys.argv[1:] == ["roots"]:
        rejected_roots()
        sys.exit()
    if sys.argv[1:] == ["first-substep"]:
        # Сценарии с отказом первого подшага: где корень, и что без порога
        for case in ("05_rs100_to01", "21_to03"):
            rejected_roots(case)
            run("float('inf')", case=case)
        sys.exit()
    for expr in ("0.98", "0.99", "0.999", "1.0", "float('inf')"):
        run(expr)
