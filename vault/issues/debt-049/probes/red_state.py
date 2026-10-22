r"""DEBT-049: что делает решатель с не конечными числами в конфиге до правки (красное состояние).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-049\probes\red_state.py
Каждый случай — configs/baseline.json (Стендинг + Кори, без CSV-таблиц) с одним
подменённым полем и историей 24 ч по 1 ч при заданном p_wf; цепочка load_config →
from_config → run. Печатается этап отказа и сообщение либо итог расчёта.

Раздел 1 — три тепловых скаляра задачи (L, μ_JT,o, μ_JT,g) × {NaN, +inf, −inf}
при p_wf = 10 МПа (выше p_b ≈ 9.4 МПа: газа нет) и 6 МПа (газовая зона у забоя).
Раздел 2 — NaN в остальных числовых полях (вариант 2 issue #81) при 6 МПа:
проверки вида `v <= 0` NaN пропускают; что дальше — неизвестно.
Каждый случай — отдельный процесс с пределом 120 с: NaN в шаге по времени
может зациклить расчёт. Рабочий каталог red_state_tmp/ удаляется в конце.
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

# (секция, поле, значение); секция "history" — поле в каждом интервале истории
THERMAL = {f"{key}_{tag}": ("thermal", key, v)
           for key in ("L_degas", "mu_JT_oil", "mu_JT_gas")
           for tag, v in (("nan", NAN), ("inf", INF), ("-inf", -INF))}

OTHER = {f"{sec}.{key}": (sec, key, NAN) for sec, key in (
    ("geometry", "r_well"), ("geometry", "R_ext"), ("geometry", "h"),
    ("rock", "porosity"), ("rock", "permeability"),
    ("pvt", "rho_o_std"), ("pvt", "rho_g_std"), ("pvt", "co_undersaturated"),
    ("relperm", "S_or"), ("relperm", "S_gc"), ("relperm", "n_o"), ("relperm", "n_g"),
    ("relperm", "kro_max"), ("relperm", "krg_max"),
    ("initial_conditions", "p0"), ("initial_conditions", "T0"),
    ("initial_conditions", "Rs0"),
    ("time", "dt_integration"), ("time", "start_day"),
    ("numerics", "dt_min"), ("numerics", "dt_max"), ("numerics", "skin"),
    ("history", "p_wf"), ("history", "dt"),
)}


def _config_path(tmp: Path, p_wf: float, change) -> Path:
    """baseline.json с одним подменённым полем и историей N_HOURS ч при p_wf, Па."""
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    raw["time"]["history"] = [{"dt": 3600.0, "control": "pressure", "p_wf": p_wf}
                              for _ in range(N_HOURS)]
    if change is not None:
        section, key, value = change
        if section == "history":
            for interval in raw["time"]["history"]:
                interval[key] = value
        else:
            raw[section][key] = value
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
                  f"T конечны: {bool(np.all(np.isfinite(T_all)))}, "
                  f"p конечны: {bool(np.all(np.isfinite(p_all)))}")
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]
        msg = str(e).splitlines()[0] if str(e) else ""
        print(f"{stage}: {type(e).__name__}: {msg[:180]}  [{Path(tb.filename).name}:{tb.lineno}]")


def run_cases(section, title, p_wf, cases):
    print(f"\n== {title}: {N_HOURS} ч при p_wf = {p_wf / 1e6:g} МПа")
    for i, (name, change) in enumerate(cases.items()):
        path = _config_path(WORK / f"s{section}_{p_wf:.0f}_{i}", p_wf, change)
        try:
            r = subprocess.run([sys.executable, __file__, "--child", str(path)],
                               cwd=SOLVER, capture_output=True, text=True,
                               encoding="utf-8", timeout=TIMEOUT)
            out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else \
                f"нет вывода, код {r.returncode}: {r.stderr.strip()[-200:]}"
        except subprocess.TimeoutExpired:
            out = f"ЗАВИС: нет итога за {TIMEOUT} с"
        print(f"{name:32s} {out}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        child(sys.argv[2])
        sys.exit(0)
    from gpn_multiphase_solver import simulator  # noqa: E402 — только путь к коду
    print(f"Код: {Path(simulator.__file__).resolve()}")
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    try:
        run_cases(1, "Раздел 1, тепловые скаляры", 10e6, {"эталон (без подмены)": None, **THERMAL})
        run_cases(1, "Раздел 1, тепловые скаляры", 6e6, {"эталон (без подмены)": None, **THERMAL})
        run_cases(2, "Раздел 2, NaN в прочих полях", 6e6, {"эталон (без подмены)": None, **OTHER})
    finally:
        shutil.rmtree(WORK)
