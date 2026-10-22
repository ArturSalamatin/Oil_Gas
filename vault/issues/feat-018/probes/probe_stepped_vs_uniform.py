"""Проба аудита FEAT-018: проверка утверждений плана до реализации.

1. Разворачивание и сообщения об ошибках: код _expand_history из плана
   (шаг 3) скопирован сюда дословно, регулярные выражения тестов шага 2
   прогоняются по его сообщениям.
2. Ключевой сценарий шага 4: 72 x 300 с против 12 x 300 с + 5 x 3600 с при
   dt_integration = 300 с на примерах 03 и 04 — побитовое совпадение на
   общих моментах записи и время прогона.

Рабочий код не меняется: история подменяется на объекте конфига.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\feat-018\\probes\\probe_stepped_vs_uniform.py
"""

import re
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

_NS = Path(__file__).resolve().parents[4] / "numerical_solver"
_PROTO = _NS / "HydroSolverPrototype" / "Prototype_1.0.3"
for p in (str(_NS), str(_PROTO)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gpn_multiphase_solver.io.config import HistoryInterval, load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

# ── Код шага 3 плана (дословно, кроме _validate_interval — упрощён) ──

_HISTORY_TIME_KEYS = frozenset({"dt", "repeat", "duration", "dt_out"})
_HISTORY_FORMS = (
    frozenset({"dt"}),
    frozenset({"dt", "repeat"}),
    frozenset({"duration", "dt_out"}),
)
_MULTIPLE_RTOL = 1e-9


def _validate_interval(h, where):
    # Упрощённо: только то, что нужно пробе (dt и p_wf при pressure).
    if h.dt <= 0:
        raise ValueError(f"{where}.dt должен быть > 0, получено {h.dt}")
    if h.control == "pressure" and h.p_wf is None:
        raise ValueError(f"{where}: control='pressure', но p_wf не задано")


def _expand_history(raw_history):
    intervals = []
    for i, raw_entry in enumerate(raw_history):
        where = f"history[{i}]"
        entry = dict(raw_entry)
        form = frozenset(entry) & _HISTORY_TIME_KEYS
        if form not in _HISTORY_FORMS:
            given = ", ".join(sorted(form)) or "нет ни dt, ни duration"
            raise ValueError(
                f"{where}: неверный набор полей времени ({given}); "
                f"допустимы dt, dt + repeat или duration + dt_out")
        if "duration" in form:
            duration = entry.pop("duration")
            dt = entry.pop("dt_out")
            if duration <= 0:
                raise ValueError(
                    f"{where}.duration должна быть > 0, получено {duration}")
            if dt <= 0:
                raise ValueError(
                    f"{where}.dt_out должен быть > 0, получено {dt}")
            n = round(duration / dt)
            if n < 1 or abs(n * dt - duration) > _MULTIPLE_RTOL * duration:
                raise ValueError(
                    f"{where}: duration = {duration} с не кратна "
                    f"dt_out = {dt} с (отношение {duration / dt:.6g}); "
                    f"задайте кратные значения или разбейте этап на блоки")
        else:
            dt = entry.pop("dt")
            n = entry.pop("repeat", 1)
            if isinstance(n, bool) or not isinstance(n, int) or n < 1:
                raise ValueError(
                    f"{where}.repeat должен быть целым >= 1, получено {n!r}")
        proto = HistoryInterval(dt=dt, **entry)
        _validate_interval(proto, where)
        intervals.extend(replace(proto) for _ in range(n))
    return intervals


# ── 1. Сообщения против регулярных выражений шага 2 ──

CASES = [
    ({"duration": 10000, "dt_out": 3600, "p_wf": 10e6}, r"history\[0\]: duration .* не кратна"),
    ({"duration": 100, "dt_out": 300, "p_wf": 10e6}, r"не кратна"),
    ({"duration": 0, "dt_out": 300, "p_wf": 10e6}, r"history\[0\]\.duration"),
    ({"duration": 3600, "dt_out": -300, "p_wf": 10e6}, r"history\[0\]\.dt_out"),
    ({"duration": 3600, "p_wf": 10e6}, r"неверный набор полей времени"),
    ({"dt_out": 300, "p_wf": 10e6}, r"неверный набор полей времени"),
    ({"repeat": 3, "p_wf": 10e6}, r"неверный набор полей времени"),
    ({"dt": 300, "duration": 3600, "dt_out": 300, "p_wf": 10e6}, r"неверный набор полей времени"),
    ({"dt": 300, "dt_out": 300, "p_wf": 10e6}, r"неверный набор полей времени"),
    ({"p_wf": 10e6}, r"неверный набор полей времени"),
    ({"dt": 300, "repeat": 0, "p_wf": 10e6}, r"history\[0\]\.repeat"),
    ({"dt": 300, "repeat": 2.5, "p_wf": 10e6}, r"history\[0\]\.repeat"),
    ({"dt": 300, "repeat": 72.0, "p_wf": 10e6}, r"history\[0\]\.repeat"),
    ({"dt": 300, "repeat": True, "p_wf": 10e6}, r"history\[0\]\.repeat"),
]
bad = 0
for entry, pattern in CASES:
    try:
        _expand_history([entry])
        print("НЕТ ОШИБКИ:", entry)
        bad += 1
    except ValueError as e:
        if not re.search(pattern, str(e)):
            print("НЕ СОВПАЛО:", pattern, "|", e)
            bad += 1
try:
    _expand_history([{"dt": 300, "repeat": 5, "p_wf": 10e6}, {"dt": 3600, "control": "pressure"}])
except ValueError as e:
    ok = re.search(r"history\[1\]: control='pressure', но p_wf", str(e)) and "history[5]" not in str(e)
    print("номер объекта JSON:", "ok" if ok else f"ПЛОХО: {e}")
print(f"сообщения: {len(CASES) - bad}/{len(CASES)} совпали")
print("0.3/0.1 ->", len(_expand_history([{"duration": 0.3, "dt_out": 0.1, "p_wf": 1e7}])), "интервала")
h = _expand_history([{"dt": 3600, "repeat": 3, "p_wf": 10e6}])
h[0].p_wf = 5e6
print("отдельные объекты:", [x.p_wf for x in h])

# ── 2. Ключевой сценарий шага 4 ──

UNIFORM = [{"dt": 300.0, "repeat": 72}]
STEPPED = [{"duration": 3600.0, "dt_out": 300.0}, {"duration": 18000.0, "dt_out": 3600.0}]


def run(example, blocks):
    config = load_config(_NS / "examples" / example / "config.json")
    control = {k: v for k, v in vars(config.time.history[0]).items() if k != "dt"}
    config.time.history = _expand_history([{**b, **control} for b in blocks])
    config.time.dt_integration = 300.0
    config.grid.N = 25
    config.output.log_level = "WARNING"
    sim, s0 = SimulatorFactory.from_config(config)
    return sim.run(s0)


for example in ("03_standing_corey", "04_table_table"):
    t0 = time.perf_counter()
    u = run(example, UNIFORM)
    t1 = time.perf_counter()
    s = run(example, STEPPED)
    t2 = time.perf_counter()
    index = {t: k for k, t in enumerate(u.times)}
    mism = []
    for j, t in enumerate(s.times):
        k = index.get(t)
        if k is None:
            mism.append((t, "time"))
            continue
        for name in ("p", "Sg", "Rs", "T", "regime"):
            if not np.array_equal(getattr(s.states[j], name), getattr(u.states[k], name)):
                mism.append((t, name))
        if s.well_data[j] != u.well_data[k]:
            mism.append((t, "well"))
        if s.balance[j] != u.balance[k]:
            mism.append((t, "balance"))
    print(f"{example}: n_saved {u.n_saved}/{s.n_saved}, t_end {u.times[-1]}/{s.times[-1]}, "
          f"расхождений {len(mism)} {mism[:5]}, время {t1 - t0:.1f} + {t2 - t1:.1f} с")
