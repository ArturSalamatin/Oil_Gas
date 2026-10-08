r"""DEBT-047: что делает решатель с недопустимыми тепловыми параметрами конфига до правки (красное состояние).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-047\probes\red_state.py
Каждый случай — configs/baseline.json (Стендинг + Кори, без CSV-таблиц: от DEBT-044
не зависит) с одним подменённым тепловым параметром и историей 24 ч по 1 ч при
p_wf = 10 МПа (выше p_b ≈ 9.4 МПа при R_s0 = 50, 350 К: газа нет) и 6 МПа (газовая
зона у забоя — в счёт входят и газовые параметры).

Раздел 1: конфиг пишется в JSON и читается load_config — после правки отказ
_validate виден той же пробой. Раздел 2 («в обход _validate»): параметр правится
в объекте конфига ПОСЛЕ load_config — так нефизичная T доходит до Simulator и
после правки, это проверка отказа по T сквозным расчётом.
Если load_config и from_config проходят, делается run и печатается итог:
диапазон T по всем записям истории, конечность и max|T − T_эталон| по всем
записям и ячейкам. Предупреждения журнала gpn_multiphase_solver — строкой «журнал».
Рабочий каталог red_state_tmp/ создаётся рядом и удаляется в конце.
"""
import json
import logging
import shutil
import sys
import traceback
import warnings
from pathlib import Path

import numpy as np

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver import simulator                      # noqa: E402
from gpn_multiphase_solver.io.config import load_config          # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory       # noqa: E402

print(f"Код: {Path(simulator.__file__).resolve()}")

BASELINE = SOLVER / "configs" / "baseline.json"
WORK = Path(__file__).resolve().parent / "red_state_tmp"
N_HOURS = 24

# (секция, параметр, значение). Штатные значения baseline: c_p,o = 2000,
# c_p,g = 1000 Дж/(кг·К); (ρc_p)_s = 1.25e6 Дж/(м³·К); λ_s = 1.5, λ_o = 0.14,
# λ_g = 0.04 Вт/(м·К); L = 1.68e5 Дж/кг.
CASES = {
    "эталон (без подмены)": None,
    "c_p_oil_zero":         ("thermal", "c_p_oil", 0.0),
    "c_p_oil_negative":     ("thermal", "c_p_oil", -2000.0),
    "c_p_oil_inf":          ("thermal", "c_p_oil", float("inf")),
    "c_p_gas_zero":         ("thermal", "c_p_gas", 0.0),
    "c_p_gas_negative":     ("thermal", "c_p_gas", -1000.0),
    "rho_cp_solid_zero":    ("rock", "rho_cp_solid", 0.0),
    "rho_cp_solid_negative": ("rock", "rho_cp_solid", -1.25e6),
    "lambda_solid_negative": ("rock", "lambda_solid", -1.5),
    "lambda_solid_inf":     ("rock", "lambda_solid", float("inf")),
    "lambda_oil_negative":  ("rock", "lambda_oil", -0.14),
    "lambda_gas_negative":  ("rock", "lambda_gas", -0.04),
    "L_degas_negative":     ("thermal", "L_degas", -1.68e5),
    # L и μ_JT план не проверяет (любой знак): NaN в них — громкий отказ или молча?
    "L_degas_nan":          ("thermal", "L_degas", float("nan")),
    "mu_JT_oil_nan":        ("thermal", "mu_JT_oil", float("nan")),
}

# В обход _validate: параметр правится после load_config (раздел 2)
BYPASS = {
    "эталон (без подмены)": None,
    "c_p_oil_zero":         ("thermal", "c_p_oil", 0.0),
    "c_p_oil_negative":     ("thermal", "c_p_oil", -2000.0),
    "rho_cp_solid_negative": ("rock", "rho_cp_solid", -1.25e6),
}


class _Records(logging.Handler):
    """Собирает предупреждения журнала gpn_multiphase_solver за один случай."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _config_path(tmp: Path, p_wf: float, change) -> Path:
    """baseline.json с одним подменённым параметром и историей N_HOURS ч при p_wf, Па."""
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    raw["time"]["history"] = [{"dt": 3600.0, "control": "pressure", "p_wf": p_wf}] * N_HOURS
    if change is not None:
        section, key, value = change
        raw[section][key] = value
    tmp.mkdir()
    path = tmp / "config.json"
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _where(e):
    tb = traceback.extract_tb(e.__traceback__)[-1]
    return f"{Path(tb.filename).name}:{tb.lineno}"


def run_cases(p_wf, cases, bypass=False):
    how = "в обход _validate (правка после load_config)" if bypass else "load_config"
    print(f"\n== {how}, from_config и run: configs/baseline.json, один тепловой параметр "
          f"подменён, {N_HOURS} ч при p_wf = {p_wf / 1e6:g} МПа")
    T_ref = None
    logger = logging.getLogger("gpn_multiphase_solver")
    for i, (name, change) in enumerate(cases.items()):
        tag = "b" if bypass else "v"
        path = _config_path(WORK / f"{tag}{p_wf:.0f}_{i}", p_wf, None if bypass else change)
        stage = "load_config"
        records = _Records()
        logger.addHandler(records)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                config = load_config(path)
                if bypass and change is not None:
                    section, key, value = change
                    setattr(getattr(config, section), key, value)
                stage = "from_config"
                sim, state = SimulatorFactory.from_config(config)
                # from_config настраивает журнал заново (уровень, обработчик);
                # обработчик пробы остаётся — он добавлен к тому же логгеру
                stage = "run"
                hist = sim.run(state)
                T_all = np.concatenate([s.T for s in hist.states])
                s = hist.states[-1]
                finite = bool(np.all(np.isfinite(T_all)))
                with np.errstate(invalid="ignore"):
                    t_min, t_max = np.nanmin(T_all), np.nanmax(T_all)
                # Эталон — первый случай; сравнение по всем записям и ячейкам
                if T_ref is None:
                    T_ref = T_all
                dev = (f", max|T − T_эт| = {np.max(np.abs(T_all - T_ref)):.3g} К"
                       if T_all.shape == T_ref.shape else "")
                out = (f"ПРОШЛИ: t = {hist.times[-1] / 3600:g} ч, S_g max {s.Sg.max():.4g}, "
                       f"T {t_min:.5g}…{t_max:.5g} К, конечны: {finite}{dev}")
            except Exception as e:
                msg = str(e).splitlines()[0] if str(e) else ""
                out = f"{stage}: {type(e).__name__}: {msg[:200]}  [{_where(e)}]"
            finally:
                logger.removeHandler(records)
        warn = sorted({f"{w.category.__name__}: {str(w.message)[:60]}" for w in caught
                       if not issubclass(w.category, DeprecationWarning)})
        print(f"{name:22s} {out}")
        for w in warn[:3]:
            print(f"{'':22s}   предупреждение {w}")
        for m in sorted(set(records.messages))[:3]:
            print(f"{'':22s}   журнал: {m[:160]}")


if __name__ == "__main__":
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    try:
        run_cases(10e6, CASES)
        run_cases(6e6, CASES)
        run_cases(6e6, BYPASS, bypass=True)
    finally:
        shutil.rmtree(WORK)
