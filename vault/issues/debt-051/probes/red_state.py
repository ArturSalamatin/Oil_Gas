r"""DEBT-051: что делает решатель с не конечными и нечисловыми значениями в конфиге (красное состояние).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-051\probes\red_state.py
Каждый случай — configs/baseline.json (Стендинг + Кори) с одним подменённым полем,
24 ч по 1 ч; цепочка load_config → from_config → run. Печатается этап отказа и
сообщение либо итог расчёта. Образец — vault/issues/debt-049/probes/red_state.py.

Раздел A — NaN во всех 30 числовых полях вне секции thermal (p_wf = 6 МПа).
Раздел B — +inf / −inf в части полей (6 МПа).
Раздел C — управление по дебиту: NaN в q_oil, min_bhp.
Раздел D — краткая форма истории {duration, dt_out}: NaN в duration, dt_out.
Раздел E — нечисловые значения: строка-число, строка, null, true.
Каждый случай — отдельный процесс с пределом 120 с. Рабочий каталог red_state_tmp/
удаляется в конце.
"""
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

BASELINE = SOLVER / "configs" / "baseline.json"
WORK = Path(__file__).resolve().parent / "red_state_tmp"
N_HOURS = 24
TIMEOUT = 120
NAN, INF = float("nan"), float("inf")
P_WF = 6e6
Q_OIL = 50.0 / 86400.0   # 50 м³ст/сут нефти, м³ст/с
MIN_BHP = 6e6

# Числовые поля вне thermal (тепловые — DEBT-047, DEBT-049): (секция, поле)
FIELDS = (
    ("geometry", "r_well"), ("geometry", "R_ext"), ("geometry", "h"),
    ("rock", "porosity"), ("rock", "permeability"), ("rock", "p_ref"),
    ("rock", "compressibility"),
    ("pvt", "rho_o_std"), ("pvt", "rho_g_std"), ("pvt", "co_undersaturated"),
    ("relperm", "S_or"), ("relperm", "S_gc"), ("relperm", "n_o"), ("relperm", "n_g"),
    ("relperm", "kro_max"), ("relperm", "krg_max"),
    ("initial_conditions", "p0"), ("initial_conditions", "T0"),
    ("initial_conditions", "Rs0"),
    ("time", "dt_integration"), ("time", "start_day"),
    ("numerics", "dt_min"), ("numerics", "dt_max"), ("numerics", "skin"),
    ("numerics", "newton_rtol"), ("numerics", "newton_atol"),
    ("numerics", "rs_switch_tol"), ("numerics", "sg_switch_tol"),
    ("history", "dt"), ("history", "p_wf"),
)

SECTION_A = {f"{s}.{k}": ("pressure", (s, k, NAN)) for s, k in FIELDS}

SECTION_B = {f"{s}.{k} = {v}": ("pressure", (s, k, v)) for s, k, v in (
    ("geometry", "R_ext", INF), ("geometry", "h", INF),
    ("rock", "permeability", INF), ("rock", "compressibility", INF),
    ("pvt", "rho_o_std", INF), ("pvt", "co_undersaturated", INF),
    ("relperm", "n_o", INF),
    ("initial_conditions", "p0", INF), ("initial_conditions", "T0", INF),
    ("initial_conditions", "Rs0", INF),
    ("time", "dt_integration", INF), ("numerics", "skin", INF),
    ("numerics", "skin", -INF), ("history", "dt", INF), ("history", "p_wf", INF),
)}

SECTION_C = {"эталон rate (без подмены)": ("rate", None),
             "history.q_oil": ("rate", ("history", "q_oil", NAN)),
             "history.min_bhp": ("rate", ("history", "min_bhp", NAN)),
             "history.q_oil = inf": ("rate", ("history", "q_oil", INF)),
             # 1000 м³ст/сут при min_bhp = 15 МПа: ограничение по забою активно
             "эталон rate_hi (без подмены)": ("rate_hi", None),
             "history.min_bhp, rate_hi": ("rate_hi", ("history", "min_bhp", NAN))}

SECTION_D = {"эталон блока (без подмены)": ("block", None),
             "history.duration": ("block", ("history", "duration", NAN)),
             "history.dt_out": ("block", ("history", "dt_out", NAN))}

SECTION_E = {f"{s}.{k} = {v!r}": ("pressure", (s, k, v)) for s, k, v in (
    ("rock", "porosity", "0.2"),          # строка-число
    ("time", "dt_integration", "3600"),
    ("initial_conditions", "p0", "abc"),   # строка
    ("geometry", "h", None),               # null
    ("rock", "permeability", True),        # bool
    ("pvt", "rho_o_std", "850"),
    ("numerics", "skin", "0"),
)}


def _history(kind: str):
    """История N_HOURS ч: по давлению, по дебиту или одним блоком {duration, dt_out}."""
    if kind == "pressure":
        return [{"dt": 3600.0, "control": "pressure", "p_wf": P_WF} for _ in range(N_HOURS)]
    if kind == "rate":
        return [{"dt": 3600.0, "control": "rate", "q_oil": Q_OIL, "min_bhp": MIN_BHP}
                for _ in range(N_HOURS)]
    if kind == "rate_hi":
        return [{"dt": 3600.0, "control": "rate", "q_oil": 1000.0 / 86400.0, "min_bhp": 15e6}
                for _ in range(N_HOURS)]
    return [{"duration": 3600.0 * N_HOURS, "dt_out": 3600.0, "control": "pressure",
             "p_wf": P_WF}]


def _config_path(tmp: Path, kind: str, change) -> Path:
    """baseline.json с историей kind и одним подменённым полем."""
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    raw["time"]["history"] = _history(kind)
    if change is not None:
        section, key, value = change
        if section == "history":
            for interval in raw["time"]["history"]:
                interval[key] = value
        else:
            raw.setdefault(section, {})[key] = value
    tmp.mkdir(parents=True)
    path = tmp / "config.json"
    # json.dumps пишет NaN/Infinity литералами — как их принял бы load_config
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def child(path: str) -> None:
    """Один случай в отдельном процессе: печатает итог одной строкой."""
    import logging
    import warnings
    import numpy as np
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    stage = "load_config"
    try:
        config = load_config(path)
        stage = "from_config"
        sim, state = SimulatorFactory.from_config(config)
        logging.disable(logging.CRITICAL)
        stage = "run"
        hist = sim.run(state)
        T_all = np.concatenate([s.T for s in hist.states])
        p_all = np.concatenate([s.p for s in hist.states])
        s = hist.states[-1]
        with np.errstate(invalid="ignore"):
            print(f"ПРОШЛИ: t = {hist.times[-1] / 3600:g} ч, S_g max {np.nanmax(s.Sg):.4g}, "
                  f"T {np.nanmin(T_all):.5g}…{np.nanmax(T_all):.5g} К, "
                  f"p {np.nanmin(p_all) / 1e6:.4g}…{np.nanmax(p_all) / 1e6:.4g} МПа, "
                  f"конечны: {bool(np.all(np.isfinite(T_all)) and np.all(np.isfinite(p_all)))}")
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]
        msg = str(e).splitlines()[0] if str(e) else ""
        print(f"{stage}: {type(e).__name__}: {msg[:150]}  [{Path(tb.filename).name}:{tb.lineno}]")


def run_cases(tag, title, cases):
    print(f"\n== {title}: {N_HOURS} ч")
    for i, (name, (kind, change)) in enumerate(cases.items()):
        path = _config_path(WORK / f"{tag}_{i}", kind, change)
        try:
            r = subprocess.run([sys.executable, __file__, "--child", str(path)],
                               cwd=SOLVER, capture_output=True, text=True,
                               encoding="utf-8", timeout=TIMEOUT)
            out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else \
                f"нет вывода, код {r.returncode}: {r.stderr.strip()[-200:]}"
        except subprocess.TimeoutExpired:
            out = f"ЗАВИС: нет итога за {TIMEOUT} с"
        print(f"{name:34s} {out}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        child(sys.argv[2])
        sys.exit(0)
    from gpn_multiphase_solver import simulator  # noqa: E402 — только путь к коду
    print(f"Код: {Path(simulator.__file__).resolve()}")
    # Необязательный аргумент — буквы разделов, например «C» или «ABE»; по умолчанию все
    only = sys.argv[1] if len(sys.argv) == 2 else "ABCDE"
    sections = {
        "A": ("Раздел A, NaN в полях вне thermal, p_wf = 6 МПа",
              {"эталон (без подмены)": ("pressure", None), **SECTION_A}),
        "B": ("Раздел B, ±inf, p_wf = 6 МПа", SECTION_B),
        "C": ("Раздел C, управление по дебиту: 50 м³ст/сут при min_bhp = 6 МПа "
              "и 1000 м³ст/сут при min_bhp = 15 МПа", SECTION_C),
        "D": ("Раздел D, краткая форма {duration, dt_out}, p_wf = 6 МПа", SECTION_D),
        "E": ("Раздел E, нечисловые значения, p_wf = 6 МПа", SECTION_E),
    }
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    try:
        for tag in only:
            run_cases(tag, *sections[tag])
    finally:
        shutil.rmtree(WORK)
