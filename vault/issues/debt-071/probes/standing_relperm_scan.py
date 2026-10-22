"""DEBT-071: S_g на пути Стендинга против таблицы ОФП — замер и эмуляция кода плана.

Режимы (запуск из numerical_solver/, печатается путь пакета):
    .venv\\Scripts\\python P scan [имя примера ...]
        Примеры с pvt.model = "standing" (без имён — все такие): min/max S_g по ВСЕМ
        принятым шагам (обёртка PrototypeHydroAdapter.solve), край таблицы ОФП прототипа,
        какие категории RELPERM дала бы проверка и когда впервые.
    .venv\\Scripts\\python P warnings [--emulate] [имя примера ...]
        Все примеры (без имён) через фабрику и Simulator.run: записи журнала «вне таблиц»
        и прочие WARNING. --emulate — код плана подставлен в памяти (install); без него —
        код пакета как есть (база — шаг 0, реализация — шаг 3: вывод как у --emulate).
    .venv\\Scripts\\python P scenarios [--emulate]
        Сценарии тестов шага 2: пример 05, укороченный, с таблицей ОФП, обрезанной до
        S_g = 0.01 / 0.1, и с таблицей, начинающейся с S_g = 0.05; baseline.
    .venv\\Scripts\\python P variants | cut21 | cut21cap
        Подбор сценария «выше таблицы» (05 при меньшем p_wf / большем R_s0; пример 21 с
        таблицей Кори, обрезанной на 0.2–0.35; то же с ограничением начального S_g 0.94).
Файлы пакета и прототипа не меняются. Таблицы ОФП проб — CSV рядом со скриптом.
"""
import logging
import sys
import time
from pathlib import Path

import numpy as np

import gpn_multiphase_solver
import radial_blackoil
import radial_blackoil.diagnostics as diag
from radial_blackoil.diagnostics import _range_tol

import gpn_multiphase_solver.factory as factory
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter, FREE_GAS_SG
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.pvt.table_full import TableFullPVT
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S
from gpn_multiphase_solver.log import user_log

SOLVER = Path.cwd()
HERE = Path(__file__).resolve().parent
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
print(f"прототип: {Path(radial_blackoil.__file__).parent}", flush=True)


# ── Код плана, шаг 1: прототип, diagnostics.py ──
def relperm_range_warnings(model, state):
    # Строки 60-64 нынешней pvt_range_warnings, без изменений
    w = []; rp = model.relperm
    sg = np.asarray(state.sg, float)
    if np.min(sg) < rp.sg[0] - _range_tol(rp.sg[0]):
        w.append(f'RELPERM Sg below table: min Sg={np.min(sg):.8g}, table min={rp.sg[0]:.8g}. Endpoint value used; no extrapolation.')
    if np.max(sg) > rp.sg[-1] + _range_tol(rp.sg[-1]):
        w.append(f'RELPERM Sg above table: max Sg={np.max(sg):.8g}, table max={rp.sg[-1]:.8g}. Endpoint value used; no extrapolation.')
    return w


# ── Код плана, шаг 2: адаптер ──
def warn_table_range(self, proto_state, t):
    if not self._check_table_range:
        return
    # Импорт при вызове, как в коде плана: подмена функций модуля (тест-шпион) видна
    from radial_blackoil.diagnostics import (pvt_range_warnings, relperm_range_warnings,
                                             warning_category)
    # getattr: исходная фабрика зовёт метод до того, как create() ставит флаг (табличный путь)
    if getattr(self, "_table_pvt", True):
        warnings = pvt_range_warnings(self._model, proto_state, free_gas_sg=FREE_GAS_SG)
    else:
        warnings = relperm_range_warnings(self._model, proto_state)
    for warning in warnings:
        category = warning_category(warning)
        if category in self._range_categories:
            continue
        self._range_categories.add(category)
        where = ("Начальное состояние" if t == 0.0
                 else f"Состояние при t = {t / DAY_TO_S:.4g} сут")
        user_log.warning(f"{where} вне таблиц: {warning}")


def install():
    """Код плана в памяти: адаптер (шаг 2) и фабрика (шаг 3)."""
    from radial_blackoil.state import BlackOilState
    diag.relperm_range_warnings = relperm_range_warnings
    PrototypeHydroAdapter.warn_table_range = warn_table_range
    orig_create = factory._create_prototype_hydro

    def create(config, grid, pvt, relperm):
        # Исходная фабрика уже проверила начальное состояние на табличной PVT
        # (категории — в _range_categories); на пути Стендинга флаг был выключен.
        adapter = orig_create(config, grid, pvt, relperm)
        table = isinstance(pvt, TableFullPVT)
        adapter._table_pvt = table
        if not table:
            adapter._check_table_range = True
            ic = config.initial_conditions
            adapter.warn_table_range(BlackOilState.undersaturated(1, ic.p0 / BAR_TO_PA, ic.Rs0), 0.0)
        return adapter

    factory._create_prototype_hydro = create


class Collect(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record)


class RunFailed(RuntimeError):
    """Отказ расчёта; messages — записи журнала WARNING до отказа."""

    def __init__(self, exc, messages):
        super().__init__(str(exc))
        self.messages = messages


def _run_logged(cfg):
    logger = logging.getLogger("gpn_multiphase_solver")
    h = Collect()
    logger.addHandler(h)
    try:
        sim, s0 = SimulatorFactory.from_config(cfg)
        logger.setLevel(logging.WARNING)
        sim.run(s0)
    except RuntimeError as exc:
        raise RunFailed(exc, [r.getMessage() for r in h.records]) from exc
    finally:
        logger.removeHandler(h)
    return [r.getMessage() for r in h.records]


def scan(names):
    """min/max S_g по всем принятым шагам; категории RELPERM и момент первого выхода."""
    seen = {}
    orig_solve = PrototypeHydroAdapter.solve

    def solve(self, state, dt, bc):
        res = orig_solve(self, state, dt, bc)
        sg = res.state.Sg
        rec = seen.setdefault(id(self), {"min": np.inf, "max": -np.inf, "n": 0, "first": {}, "rp": self._model.relperm})
        rec["min"] = min(rec["min"], float(np.min(sg)))
        rec["max"] = max(rec["max"], float(np.max(sg)))
        rec["n"] += 1
        proto = type("S", (), {"sg": sg})()
        for w in relperm_range_warnings(self._model, proto):
            cat = diag.warning_category(w)
            rec["first"].setdefault(cat, (state.t + dt, w))
        return res

    PrototypeHydroAdapter.solve = solve
    for name in names:
        cfg = load_config(SOLVER / "examples" / name / "config.json")
        t0 = time.perf_counter()
        seen.clear()
        sim, s0 = SimulatorFactory.from_config(cfg)
        logging.getLogger("gpn_multiphase_solver").setLevel(logging.WARNING)
        sim.run(s0)
        rec = next(iter(seen.values()))
        rp = rec["rp"]
        print(f"{name:28s} ОФП {cfg.relperm.model:5s} таблица S_g {rp.sg[0]:.3g}…{rp.sg[-1]:.3g} "
              f"({len(rp.sg)} узлов); принятых шагов {rec['n']}; S_g min {rec['min']:.3e}, max {rec['max']:.6g}; "
              f"{time.perf_counter() - t0:.1f} с", flush=True)
        for cat, (t, w) in rec["first"].items():
            print(f"    выход: t = {t / DAY_TO_S:.4g} сут: {w}")
    PrototypeHydroAdapter.solve = orig_solve


def warnings_all(names, emulate):
    if emulate:
        install()
        print("эмуляция кода плана (install)", flush=True)
    total = 0
    for name in names:
        msgs = _run_logged(load_config(SOLVER / "examples" / name / "config.json"))
        rng = [m for m in msgs if "вне таблиц" in m]
        other = [m for m in msgs if "вне таблиц" not in m]
        total += len(rng)
        print(f"{name:30s} «вне таблиц»: {len(rng)}, прочих WARNING: {len(other)}", flush=True)
        for m in rng:
            print(f"    {m}")
        for m in other:
            print(f"    [прочее] {m[:60]}")
    print(f"итог: записей «вне таблиц» {total} в {len(names)} примерах")


def scenarios(emulate):
    """Сценарии тестов шага 2: пример 05, первые hours ч, таблица ОФП из CSV рядом с пробой."""
    if emulate:
        install()
        print("эмуляция кода плана (install)", flush=True)
    ex05 = SOLVER / "examples" / "05_standing_table_rp" / "config.json"
    # relperm_to_001.csv (до S_g = 0.01, k_rg края 0.001) при штатном 05 не сходится уже на
    # первом часе: выше края k_ro = 0.98 и k_rg = 0.001 постоянны, нефть уходит, газ стоит,
    # S_g у забоя → 0.92 (scenarios.out.txt первой версии пробы). Обрезка — до 0.1, R_s0 = 100.
    cases = [
        ("05, 6 ч, таблица до S_g = 0.01", "relperm_to_001.csv", 6, None),
        ("05, R_s0 = 100, 6 ч, таблица до S_g = 0.1", "relperm_to_01.csv", 6, 100.0),
        ("05, R_s0 = 100, 6 ч, таблица примера", None, 6, 100.0),
        ("05, 6 ч, таблица с S_g = 0.05", "relperm_from_005.csv", 6, None),
        ("05, 6 ч, таблица примера", None, 6, None),
        ("baseline (Стендинг + Кори), полностью", "baseline", None, None),
    ]
    for label, csv, hours, rs0 in cases:
        if csv == "baseline":
            cfg = load_config(SOLVER / "configs" / "baseline.json")
        else:
            # load_config разворачивает историю в интервалы по dt_out (05: 72 по 1 ч)
            cfg = load_config(ex05)
            if csv is not None:
                cfg.relperm.file = str(HERE / csv)
            cfg.time.history = cfg.time.history[:hours]
            if rs0 is not None:
                cfg.initial_conditions.Rs0 = rs0
        t0 = time.perf_counter()
        try:
            msgs = _run_logged(cfg)
        except RunFailed as exc:
            print(f"\n=== {label}: отказ, {time.perf_counter() - t0:.2f} с; записей WARNING до отказа "
                  f"{len(exc.messages)} ===\n   {str(exc)[:160]}")
            for m in exc.messages:
                print(f"   {m}")
            continue
        print(f"\n=== {label}: записей WARNING {len(msgs)}, {time.perf_counter() - t0:.2f} с ===")
        for m in msgs:
            print(f"   {m}")


def variants():
    """Пример 05 с меньшим p_wf / большим R_s0: max S_g по принятым шагам — подбор сценария «выше таблицы»."""
    ex05 = SOLVER / "examples" / "05_standing_table_rp" / "config.json"
    orig_solve = PrototypeHydroAdapter.solve
    box = {}

    def solve(self, state, dt, bc):
        res = orig_solve(self, state, dt, bc)
        box["max"] = max(box.get("max", 0.0), float(np.max(res.state.Sg)))
        box["n"] = box.get("n", 0) + 1
        box.setdefault("t_first", {})
        for edge in (0.1, 0.2, 0.4):
            if np.max(res.state.Sg) > edge:
                box["t_first"].setdefault(edge, state.t + dt)
        return res

    PrototypeHydroAdapter.solve = solve
    for p_wf, rs0, hours in [(4e6, 50, 6), (2e6, 50, 6), (8e6, 100, 6), (4e6, 100, 6), (2e6, 100, 6)]:
        # load_config разворачивает историю в интервалы по dt_out (05: 72 по 1 ч)
        cfg = load_config(ex05)
        cfg.time.history = cfg.time.history[:hours]
        for interval in cfg.time.history:
            interval.p_wf = p_wf
        cfg.initial_conditions.Rs0 = rs0
        box.clear()
        t0 = time.perf_counter()
        try:
            sim, s0 = SimulatorFactory.from_config(cfg)
            logging.getLogger("gpn_multiphase_solver").setLevel(logging.WARNING)
            sim.run(s0)
            status = "сошёлся"
        except Exception as exc:  # noqa: BLE001 — проба: печать причины
            status = f"отказ: {str(exc)[:90]}"
        firsts = ", ".join(f"S_g > {e}: {t / 3600:.3g} ч" for e, t in box.get("t_first", {}).items())
        print(f"05, p_wf = {p_wf / 1e6:g} МПа, R_s0 = {rs0}, {hours} ч: {status}; принятых {box.get('n', 0)}, "
              f"max S_g {box.get('max', 0):.4g}; {firsts}; {time.perf_counter() - t0:.2f} с", flush=True)
    PrototypeHydroAdapter.solve = orig_solve


def cut21():
    """Пример 21 (Стендинг + Кори, max S_g 0.41): Кори примера, протабулированная до S_g = cut, — выход выше края в расчёте?"""
    from gpn_multiphase_solver.factory import create_relperm
    ex21 = SOLVER / "examples" / "21_rs100_cooling" / "config.json"
    corey = create_relperm(load_config(ex21))
    install()
    # cut = 1.0 — контроль: та же таблица, что фабрика строит из Кори (101 узел, k_ro = 0 с 0.95)
    for cut, days in [(1.0, 5), (0.3, 30), (0.3, 5), (0.35, 5), (0.2, 5)]:
        sg = np.round(np.linspace(0.0, cut, int(round(cut / 0.01)) + 1), 10)
        csv = HERE / f"relperm_corey21_to_{cut:g}.csv"
        rows = "\n".join(f"{s:.10g},{float(corey.kro(np.array([s]))[0]):.10g},{float(corey.krg(np.array([s]))[0]):.10g}" for s in sg)
        csv.write_text("Sg,kro,krg\n" + rows + "\n", encoding="utf-8")
        cfg = load_config(ex21)
        cfg.relperm.model = "table"
        cfg.relperm.file = str(csv)
        cfg.time.history = cfg.time.history[:days]
        t0 = time.perf_counter()
        try:
            msgs = _run_logged(cfg)
        except RunFailed as exc:
            print(f"21, Кори до S_g = {cut}, {days} сут: отказ, {time.perf_counter() - t0:.2f} с, записей WARNING "
                  f"до отказа {len(exc.messages)}: {str(exc)[:120]}", flush=True)
            for m in exc.messages:
                print(f"   {m}")
            continue
        print(f"21, Кори до S_g = {cut}, {days} сут: записей WARNING {len(msgs)}, {time.perf_counter() - t0:.2f} с", flush=True)
        for m in msgs:
            print(f"   {m}")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "variants":
        variants()
        sys.exit()
    if mode == "cut21":
        cut21()
        sys.exit()
    if mode == "cut21cap":
        # Причина отказа — отсутствие ограничения начального S_g (BUG-018) или сама таблица?
        # _sg_activation_cap даёт None, если в таблице нет узла с k_ro = 0; здесь вместо None —
        # 0.94, как у контрольной таблицы Кори (последний узел с k_ro > 0).
        import radial_blackoil.blackoil as bo
        orig_cap = bo._sg_activation_cap
        bo._sg_activation_cap = lambda rp: orig_cap(rp) if orig_cap(rp) is not None else 0.94
        print("ограничение начального S_g: None → 0.94 (подмена в памяти)", flush=True)
        cut21()
        sys.exit()
    emulate = "--emulate" in sys.argv
    names = [a for a in sys.argv[2:] if a != "--emulate"]
    all_names = sorted(p.parent.name for p in (SOLVER / "examples").glob("*/config.json"))
    if mode == "scan":
        names = names or [n for n in all_names
                          if load_config(SOLVER / "examples" / n / "config.json").pvt.model == "standing"]
        scan(names)
    elif mode == "warnings":
        warnings_all(names or all_names, emulate)
    elif mode == "scenarios":
        scenarios(emulate)
